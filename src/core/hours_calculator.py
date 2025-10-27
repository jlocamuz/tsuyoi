"""
Calculador de Horas según Normativa Argentina - VERSIÓN FINAL
Con nuevas reglas específicas de horas extra e incidencias
CORREGIDO: Ahora incluye contador de días de ausencia
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo  # TZ Argentina
from config.default_config import DEFAULT_CONFIG


class ArgentineHoursCalculatorEnhanced:
    """Calculador de horas según normativa laboral argentina - versión final"""
    
    def __init__(self):
        self.jornada_completa = DEFAULT_CONFIG['jornada_completa_horas']
        self.hora_nocturna_inicio = int(DEFAULT_CONFIG['hora_nocturna_inicio'])
        self.hora_nocturna_fin = int(DEFAULT_CONFIG['hora_nocturna_fin'])
        self.sabado_limite = int(DEFAULT_CONFIG['sabado_limite_hora'])
        self.tolerancia_minutos = int(DEFAULT_CONFIG['tolerancia_minutos'])
        self.fragmento_minutos = int(DEFAULT_CONFIG['fragmento_minutos'])

        # Zona horaria de Argentina
        self.tz = ZoneInfo("America/Argentina/Buenos_Aires")
    
    def process_employee_data(self, day_summaries: List[Dict], employee_info: Dict,
                              previous_pending_hours: float = 0, holidays: List[Dict] = None) -> Dict:
        """
        Procesa los datos de un empleado desde day summaries - VERSIÓN FINAL
        Preserva datos crudos y aplica nuevas reglas de horas extra
        CORREGIDO: Ahora cuenta días de ausencia
        """
        daily_data: List[Dict] = []
        totals = {
            'total_days_worked': 0,
            'total_hours_worked': 0,
            'total_regular_hours': 0,
            'total_extra_hours_50': 0,
            'total_extra_hours_100': 0,
            'total_night_hours': 0,
            'total_pending_hours': previous_pending_hours,
            'total_absence_days': 0  # AGREGAR CONTADOR DE AUSENCIAS
        }
        
        for day_summary in day_summaries:
            date_str = day_summary.get('referenceDate', day_summary.get('date'))
            date = datetime.strptime(date_str, '%Y-%m-%d')

            # Datos crudos
            raw_entries = day_summary.get('entries', [])
            time_slots = day_summary.get('timeSlots', [])
            incidences = day_summary.get('incidences', []) or []
            
            # Horas trabajadas
            hours_worked_api = day_summary.get('hours', {}).get('worked', 0) or day_summary.get('totalHours', 0)
            hours_worked_real = self._calculate_total_worked_hours(raw_entries)
            hours_worked = hours_worked_real if hours_worked_real > 0 else hours_worked_api
            
            # Flags
            is_holiday   = bool(day_summary.get('holidays'))
            has_time_off = bool(day_summary.get('timeOffRequests'))
            absence_keys = {'ABSENCE', 'ABSENT'}  # añade 'UNJUSTIFIED_ABSENCE','NO_SHOW' si aplican
            has_absence  = any(k in absence_keys for k in incidences)
            is_workday   = bool(day_summary.get('isWorkday', True))

            # CONTAR DÍAS DE AUSENCIA (INDEPENDIENTEMENTE DE HORAS TRABAJADAS)
            if has_absence:
                totals['total_absence_days'] += 1

            # ✅ Mantener ausencias aunque tengan 0 horas; descartar solo si NO tiene horas, NO licencia y NO ausencia
            if hours_worked == 0 and not has_time_off and not has_absence:
                continue

            # Turno programado y entradas/salidas
            turno_inicio = time_slots[0].get('startTime', '') if time_slots else ''
            turno_fin    = time_slots[0].get('endTime', '') if time_slots else ''
            entrada_local, salida_local, comienzo_jornada, fin_jornada = self._parse_real_entry_times(raw_entries)

            # Horas nocturnas
            night_hours = self.calcular_horas_nocturnas(entrada_local, salida_local)

            # Distribución de horas
            day_hours = self.calculate_hour_distribution(
                hours_worked=hours_worked,
                date=date,
                is_holiday=is_holiday,
                has_time_off=has_time_off,
                night_hours=night_hours,
                entrada_local=entrada_local,
                salida_local=salida_local,
                time_slots=time_slots,
                is_workday=is_workday,
                incidences=incidences
            )

            # Totales
            if hours_worked > 0:
                totals['total_days_worked'] += 1
                totals['total_hours_worked'] += day_hours['hours_worked']
                totals['total_regular_hours'] += day_hours['regular_hours']
                totals['total_extra_hours_50'] += day_hours['extra_hours_50']
                totals['total_extra_hours_100'] += day_hours['extra_hours_100']
                totals['total_night_hours'] += day_hours['night_hours']
                if not has_time_off and not has_absence:
                    totals['total_pending_hours'] += day_hours['pending_hours']

            # Fila de salida
            daily_data.append({
                'employee_id': employee_info.get('employeeInternalId'),
                'date': date.strftime('%Y-%m-%d'),
                'day_of_week': self.get_day_of_week_spanish(date),
                'scheduled_start': turno_inicio,
                'scheduled_end': turno_fin,
                'start_time': comienzo_jornada,
                'end_time': fin_jornada,
                'hours_worked': day_hours['hours_worked'],
                'regular_hours': day_hours['regular_hours'],
                'extra_hours_50': day_hours['extra_hours_50'],
                'extra_hours_100': day_hours['extra_hours_100'],
                'night_hours': day_hours['night_hours'],
                'pending_hours': day_hours['pending_hours'] if not (has_time_off or has_absence) else 0,
                'is_holiday': is_holiday,
                'holiday_name': day_summary.get('holidays', [{}])[0].get('name') if is_holiday else None,
                'has_time_off': has_time_off,
                'time_off_name': day_summary.get('timeOffRequests', [{}])[0].get('name') if has_time_off else None,
                'has_absence': has_absence,

                # Para Excel detallado:
                'raw_entries': raw_entries,
                'time_slots': time_slots,
                'day_summary_id': day_summary.get('id'),
                'weekday': day_summary.get('weekday', ''),
                'hours_data': day_summary.get('hours', {}),
                'incidences': incidences,
            })

        # Compensaciones
        compensations = self.calculate_compensations(
            totals['total_extra_hours_50'], 
            totals['total_extra_hours_100'], 
            totals['total_pending_hours']
        )
        
        return {
            'employee_info': employee_info,
            'daily_data': daily_data,
            'totals': totals,
            'compensations': compensations
        }
    
    def calculate_hour_distribution(self, hours_worked: float, date: datetime, 
                                    is_holiday: bool = False, has_time_off: bool = False,
                                    night_hours: float = 0,
                                    entrada_local: Optional[datetime] = None,
                                    salida_local: Optional[datetime] = None,
                                    time_slots: Optional[List[Dict]] = None,
                                    is_workday: bool = True,
                                    incidences: List[str] = None) -> Dict:
        """
        VERSIÓN ACTUALIZADA con nuevas reglas de horas extra
        """
        if hours_worked == 0:
            return {
                'hours_worked': 0, 'regular_hours': 0, 'extra_hours_50': 0,
                'extra_hours_100': 0, 'night_hours': night_hours, 'pending_hours': 0
            }

        day_of_week = date.weekday()  # 0=Lunes ... 6=Domingo
        regular_hours = 0.0
        extra_hours_50 = 0.0
        extra_hours_100 = 0.0
        pending_hours = 0.0

        has_late = incidences and 'LATE' in incidences

        # Feriados: todo al 100%
        if is_holiday:
            extra_hours_100 = hours_worked

        elif day_of_week == 6:  # Domingo
            if not is_workday:
                regular_hours = 0.0
                extra_hours_100 = hours_worked
            else:
                reg, e100 = self._sunday_from_times(entrada_local, salida_local, time_slots or [])
                total_calc = reg + e100
                if total_calc > 0 and abs(total_calc - hours_worked) > 0.01:
                    scale = hours_worked / total_calc
                    regular_hours = reg * scale
                    extra_hours_100 = e100 * scale
                else:
                    regular_hours = reg
                    extra_hours_100 = e100

        elif day_of_week == 5:  # Sábado
            if entrada_local and salida_local:
                reg, _, e100 = self._saturday_new_calculation(entrada_local, salida_local, time_slots or [])
            else:
                reg = min(hours_worked, self.jornada_completa)
                e100 = max(0, hours_worked - self.jornada_completa)
            
            regular_hours = reg
            extra_hours_100 = e100

        else:  # Lunes a viernes
            if hours_worked <= self.jornada_completa:
                regular_hours = hours_worked
                pending_hours = max(0, self.jornada_completa - hours_worked)
            else:
                regular_hours = self.jornada_completa
                extra_hours = hours_worked - self.jornada_completa
                
                # Nuevas reglas de distribución de extras
                if extra_hours <= 2.0:
                    extra_hours_50 = extra_hours
                else:
                    extra_hours_50 = 2.0
                    extra_hours_100 = extra_hours - 2.0

        return {
            'hours_worked': hours_worked,
            'regular_hours': round(regular_hours, 2),
            'extra_hours_50': round(extra_hours_50, 2),
            'extra_hours_100': round(extra_hours_100, 2),
            'night_hours': night_hours,
            'pending_hours': round(pending_hours, 2)
        }

    def _saturday_new_calculation(self, entrada_local: datetime, salida_local: datetime, time_slots: List[Dict]) -> Tuple[float, float, float]:
        """Cálculo específico para sábados según documento v.2.0"""
        
        inicio_sabado = entrada_local.replace(hour=8, minute=0, second=0, microsecond=0)
        fin_sabado = entrada_local.replace(hour=13, minute=0, second=0, microsecond=0)

        minutos_tardanza = max(0, (entrada_local - inicio_sabado).total_seconds() / 60.0)
        minutos_retiro_anticipado = max(0, (fin_sabado - salida_local).total_seconds() / 60.0) if salida_local < fin_sabado else 0

        base_hours_100 = 4.0
        if minutos_tardanza > 30: base_hours_100 -= 1.0
        elif minutos_tardanza > 6: base_hours_100 -= 0.5

        if minutos_retiro_anticipado > 30: base_hours_100 -= 1.0
        elif minutos_retiro_anticipado > 6: base_hours_100 -= 0.5

        base_hours_100 = max(0.0, base_hours_100)

        extra_hours_100 = 0.0
        if salida_local > fin_sabado:
            minutos_extra = (salida_local - fin_sabado).total_seconds() / 60.0
            if minutos_extra > 60:
                extra_hours_100 = 1.0
            elif minutos_extra > 30:
                extra_hours_100 = 0.5

        total_hours_100 = base_hours_100 + extra_hours_100
        return 0.0, 0.0, round(total_hours_100, 2)

    def calculate_compensations(self, extra_hours_50: float, extra_hours_100: float,
                                pending_hours: float) -> Dict:
        compensated_with_50 = 0
        compensated_with_100 = 0
        remaining_pending_hours = pending_hours
        
        if remaining_pending_hours > 0 and extra_hours_50 > 0:
            compensated_with_50 = min(remaining_pending_hours, extra_hours_50)
            remaining_pending_hours -= compensated_with_50
        
        if remaining_pending_hours > 0 and extra_hours_100 > 0:
            max_compensation_with_100 = extra_hours_100 * 1.5
            compensated_with_100 = min(remaining_pending_hours, max_compensation_with_100)
            remaining_pending_hours -= compensated_with_100
        
        net_extra_hours_50 = extra_hours_50 - compensated_with_50
        net_extra_hours_100 = extra_hours_100 - (compensated_with_100 / 1.5)
        
        return {
            'compensated_with_50': round(compensated_with_50, 2),
            'compensated_with_100': round(compensated_with_100, 2),
            'net_extra_hours_50': round(net_extra_hours_50, 2),
            'net_extra_hours_100': round(net_extra_hours_100, 2),
            'remaining_pending_hours': round(remaining_pending_hours, 2)
        }

    def calcular_horas_nocturnas(self, hora_entrada: datetime, hora_salida: datetime) -> float:
        if not hora_entrada or not hora_salida or hora_salida <= hora_entrada:
            return 0.0
        
        entrada_local = hora_entrada.astimezone(self.tz)
        salida_local = hora_salida.astimezone(self.tz)

        start_nocturna = entrada_local.replace(hour=int(DEFAULT_CONFIG['hora_nocturna_inicio']), minute=0, second=0, microsecond=0)
        end_nocturna = entrada_local.replace(hour=int(DEFAULT_CONFIG['hora_nocturna_fin']), minute=0, second=0, microsecond=0)
        if int(DEFAULT_CONFIG['hora_nocturna_fin']) <= int(DEFAULT_CONFIG['hora_nocturna_inicio']):
            end_nocturna += timedelta(days=1)

        inicio = max(entrada_local, start_nocturna)
        fin = min(salida_local, end_nocturna)

        if fin <= inicio:
            return 0.0

        return round((fin - inicio).total_seconds() / 3600.0, 2)
    
    def get_day_of_week_spanish(self, date: datetime) -> str:
        days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return days[date.weekday()]

    def _horas_interseccion(self, a1: Optional[datetime], a2: Optional[datetime],
                             b1: Optional[datetime], b2: Optional[datetime]) -> float:
        if not a1 or not a2 or not b1 or not b2:
            return 0.0
        ini = max(a1, b1)
        fin = min(a2, b2)
        if fin <= ini:
            return 0.0
        return (fin - ini).total_seconds() / 3600.0

    def _sunday_from_times(self, entrada_local: Optional[datetime], salida_local: Optional[datetime],
                           time_slots: List[Dict]) -> Tuple[float, float]:
        if not entrada_local or not salida_local or salida_local <= entrada_local:
            return 0.0, 0.0

        work_ini = entrada_local
        work_fin = salida_local

        sched_start = sched_end = None
        if time_slots and time_slots[0]:
            st = time_slots[0].get("startTime")
            et = time_slots[0].get("endTime")
            if st and ":" in st:
                h, m = [int(x) for x in st.split(":")]
                sched_start = entrada_local.replace(hour=h, minute=m, second=0, microsecond=0)
            if et and ":" in et:
                h, m = [int(x) for x in et.split(":")]
                sched_end = entrada_local.replace(hour=h, minute=m, second=0, microsecond=0)

        if not sched_start or not sched_end:
            reg = 0.0
            e100 = (work_fin - work_ini).total_seconds() / 3600.0
            return round(reg, 2), round(e100, 2)

        reg = self._horas_interseccion(work_ini, work_fin, sched_start, sched_end)
        e100 = 0.0
        if work_fin > sched_end:
            extra_ini = max(work_ini, sched_end)
            extra_fin = work_fin
            e100 = self._horas_interseccion(extra_ini, extra_fin, extra_ini, extra_fin)

        return round(reg, 2), round(e100, 2)

    def _parse_real_entry_times(self, entries: List[Dict]) -> Tuple[Optional[datetime], Optional[datetime], str, str]:
        """Devuelve (entrada_local, salida_local, comienzo_hhmm, fin_hhmm) en TZ AR. Primera START y última END"""
        if not entries:
            return None, None, '', ''

        sorted_entries = sorted(entries, key=lambda x: x.get('time', ''))
        first_start = None
        last_end = None
        
        for entry in sorted_entries:
            if entry.get('type') == 'START' and entry.get('time'):
                if first_start is None:
                    first_start = entry
            elif entry.get('type') == 'END' and entry.get('time'):
                last_end = entry

        entrada_local = None
        salida_local = None
        comienzo_jornada = ''
        fin_jornada = ''
        
        try:
            if first_start:
                entrada_local = datetime.fromisoformat(first_start['time'].replace('Z', '+00:00')).astimezone(self.tz)
                comienzo_jornada = entrada_local.strftime('%H:%M')
            if last_end:
                salida_local = datetime.fromisoformat(last_end['time'].replace('Z', '+00:00')).astimezone(self.tz)
                fin_jornada = salida_local.strftime('%H:%M')
        except Exception:
            pass
            
        return entrada_local, salida_local, comienzo_jornada, fin_jornada

    def _calculate_total_worked_hours(self, entries: List[Dict]) -> float:
        """Suma todos los períodos START/END"""
        if not entries:
            return 0.0
        
        sorted_entries = sorted(entries, key=lambda x: x.get('time', ''))
        total_hours = 0.0
        current_start = None
        
        for entry in sorted_entries:
            entry_type = entry.get('type')
            time_str = entry.get('time', '')
            try:
                if time_str:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00')).astimezone(self.tz)
                else:
                    continue
            except:
                continue
            
            if entry_type == 'START':
                current_start = dt
            elif entry_type == 'END' and current_start:
                period_hours = (dt - current_start).total_seconds() / 3600.0
                total_hours += period_hours
                current_start = None
        
        return round(total_hours, 2)


# Alias para compatibilidad con código existente
ArgentineHoursCalculator = ArgentineHoursCalculatorEnhanced