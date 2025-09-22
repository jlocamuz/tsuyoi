"""
Calculador de Horas según Normativa Argentina - VERSIÓN FINAL
Con nuevas reglas específicas de horas extra y incidencias
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
        """
        daily_data: List[Dict] = []
        totals = {
            'total_days_worked': 0,
            'total_hours_worked': 0,
            'total_regular_hours': 0,
            'total_extra_hours_50': 0,
            'total_extra_hours_100': 0,
            'total_night_hours': 0,
            'total_pending_hours': previous_pending_hours
        }
        
        # Procesar cada day summary
        for day_summary in day_summaries:
            date_str = day_summary.get('referenceDate', day_summary.get('date'))
            date = datetime.strptime(date_str, '%Y-%m-%d')

            # Datos crudos para Excel detallado - MOVER ANTES DEL CÁLCULO
            raw_entries = day_summary.get('entries', [])
            time_slots = day_summary.get('timeSlots', [])
            incidences = day_summary.get('incidences', [])
            
            # Flags e información base
            hours_worked_api = day_summary.get('hours', {}).get('worked', 0) or day_summary.get('totalHours', 0)
            
            # CALCULAR HORAS REALES sumando todos los períodos trabajados
            hours_worked_real = self._calculate_total_worked_hours(raw_entries)
            
            # Usar las horas reales calculadas si son diferentes de la API
            hours_worked = hours_worked_real if hours_worked_real > 0 else hours_worked_api
            
            is_holiday = bool(day_summary.get('holidays') and len(day_summary.get('holidays', [])) > 0)
            has_time_off = bool(day_summary.get('timeOffRequests') and len(day_summary.get('timeOffRequests', [])) > 0)
            has_absence = bool(day_summary.get('incidences') and 'ABSENT' in day_summary.get('incidences', []))
            is_workday = bool(day_summary.get('isWorkday', True))

            if hours_worked == 0 and not has_time_off:
                continue

            # Turno programado (primer time slot si existe)
            turno_inicio = time_slots[0].get('startTime', '') if time_slots else ''
            turno_fin = time_slots[0].get('endTime', '') if time_slots else ''

            # Entrada/Salida reales a TZ Argentina
            entries = day_summary.get('entries') or []
            entrada_local, salida_local, comienzo_jornada, fin_jornada = self._parse_real_entry_times(entries)
            
            if hours_worked == 0 and not has_time_off:
                continue

            # Turno programado (primer time slot si existe)
            turno_inicio = time_slots[0].get('startTime', '') if time_slots else ''
            turno_fin = time_slots[0].get('endTime', '') if time_slots else ''

            # Entrada/Salida reales a TZ Argentina
            entries = day_summary.get('entries') or []
            entrada_local, salida_local, comienzo_jornada, fin_jornada = self._parse_real_entry_times(entries)

            # Horas nocturnas
            night_hours = self.calcular_horas_nocturnas(entrada_local, salida_local)

            # Distribución de horas - ACTUALIZADA con incidencias
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
                incidences=incidences  # PASAR LAS INCIDENCIAS
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

            # Fila de salida - MEJORADA con datos crudos e incidencias
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
                
                # CAMPOS EXISTENTES para Excel detallado
                'raw_entries': raw_entries,
                'time_slots': time_slots,
                'day_summary_id': day_summary.get('id'),
                'weekday': day_summary.get('weekday', ''),
                'hours_data': day_summary.get('hours', {}),
                
                # NUEVO CAMPO: incidencias del day summary
                'incidences': incidences,  # AGREGAR INCIDENCIAS
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

        # Detectar tardanza
        has_late = incidences and 'LATE' in incidences

        # Feriados: todo al 100%
        if is_holiday:
            extra_hours_100 = hours_worked

        elif day_of_week == 6:  # DOMINGO
            if not is_workday:
                regular_hours = 0.0
                extra_hours_100 = hours_worked
            else:
                reg, e100 = self._sunday_from_times(entrada_local, salida_local, time_slots or [])
                total_calc = reg + e100
                if total_calc > 0 and abs(total_calc - hours_worked) > 0.01:
                    factor = hours_worked / total_calc
                    reg, e100 = reg * factor, e100 * factor
                regular_hours = round(reg, 2)
                extra_hours_100 = round(e100, 2)

        elif day_of_week == 5:  # SÁBADO - NUEVAS REGLAS
            if entrada_local and salida_local:
                reg, e50, e100 = self._calculate_saturday_extras_new_rules(
                    entrada_local, salida_local, time_slots or [], has_late
                )
                regular_hours = round(reg, 2)
                extra_hours_50 = round(e50, 2)
                extra_hours_100 = round(e100, 2)
            else:
                # Fallback: asumir que es sábado estándar
                extra_hours_100 = min(4.0, hours_worked)

        else:  # LUNES A VIERNES - NUEVAS REGLAS
            if entrada_local and salida_local and time_slots:
                # Usar las horas totales trabajadas ya calculadas
                total_hours_worked = hours_worked
                
                # Calcular duración de jornada programada
                start_str = time_slots[0].get("startTime", "09:00")
                end_str = time_slots[0].get("endTime", "18:00")
                start_h, start_m = [int(x) for x in start_str.split(":")]
                end_h, end_m = [int(x) for x in end_str.split(":")]
                
                jornada_programada_horas = end_h - start_h + (end_m - start_m) / 60.0
                
                # Horas regulares: máximo hasta la jornada programada
                regular_hours = min(total_hours_worked, jornada_programada_horas)
                
                # Horas extras solo si trabajó más allá de la jornada programada
                extra_hours_50 = 0.0
                extra_hours_100 = 0.0
                
                if total_hours_worked > jornada_programada_horas:
                    minutos_extra = (total_hours_worked - jornada_programada_horas) * 60.0
                    
                    # Aplicar reglas específicas de abono:
                    # >30 min y ≤60 min = se abona 0.5 horas
                    # >60 min = se abona 1.0 hora
                    if minutos_extra > 60:  # Más de 1 hora
                        extra_hours_50 = 1.0
                    elif minutos_extra > 30:  # Más de 30 minutos pero ≤60 minutos
                        extra_hours_50 = 0.5
                    # ≤30 minutos = no se abona extra (extra_hours_50 = 0.0)
                
                # Horas pendientes solo si trabajó menos de la jornada completa
                if not has_time_off and total_hours_worked < jornada_programada_horas:
                    pending_hours = jornada_programada_horas - total_hours_worked
                    
            else:
                # Fallback sin datos de tiempo real
                if hours_worked <= self.jornada_completa:
                    regular_hours = hours_worked
                    if not has_time_off and hours_worked < self.jornada_completa:
                        pending_hours = self.jornada_completa - hours_worked
                else:
                    regular_hours = self.jornada_completa
                    extra_total = hours_worked - self.jornada_completa
                    # Aplicar nuevas reglas incluso en fallback
                    if extra_total >= 1:
                        extra_hours_50 = 1.0
                    elif extra_total >= 0.5:
                        extra_hours_50 = 0.5

        return {
            'hours_worked': round(hours_worked, 2),
            'regular_hours': round(regular_hours, 2),
            'extra_hours_50': round(extra_hours_50, 2),
            'extra_hours_100': round(extra_hours_100, 2),
            'night_hours': round(night_hours, 2),
            'pending_hours': round(pending_hours, 2)
        }

    def _calculate_weekday_extras_new_rules(self, entrada_local: datetime, salida_local: datetime, 
                                          time_slots: List[Dict]) -> Tuple[float, float, float]:
        """
        NUEVAS REGLAS para días de semana (L-V):
        - Extras al 50% solo después del turno laboral
        - Media hora si permanece >30min (con 20min no se abona)
        - Una hora si permanece >1h (con 40min solo se abona media hora)
        """
        if not entrada_local or not salida_local or salida_local <= entrada_local:
            return 0.0, 0.0, 0.0
            
        if not time_slots or not time_slots[0] or not time_slots[0].get("endTime"):
            return 0.0, 0.0, 0.0

        # Fin de jornada programada
        end_str = time_slots[0]["endTime"]
        end_h, end_m = [int(x) for x in end_str.split(":")]
        fin_jornada_prog = entrada_local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

        # Calcular total de horas trabajadas
        total_hours_worked = (salida_local - entrada_local).total_seconds() / 3600.0

        # Calcular duración de jornada programada
        start_str = time_slots[0].get("startTime", "09:00")
        start_h, start_m = [int(x) for x in start_str.split(":")]
        inicio_jornada_prog = entrada_local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        jornada_programada_horas = (fin_jornada_prog - inicio_jornada_prog).total_seconds() / 3600.0

        # Horas regulares: máximo hasta la jornada programada
        regular_hours = min(total_hours_worked, jornada_programada_horas)

        # Horas extras solo si trabajó más allá de la jornada programada
        extra_hours_50 = 0.0
        extra_hours_100 = 0.0
        
        if total_hours_worked > jornada_programada_horas:
            minutos_extra = (total_hours_worked - jornada_programada_horas) * 60.0
            
            # Aplicar reglas específicas de abono:
            # >30 min y ≤60 min = se abona 0.5 horas
            # >60 min = se abona 1.0 hora  
            if minutos_extra > 60:  # Más de 1 hora
                extra_hours_50 = 1.0
            elif minutos_extra > 30:  # Más de 30 minutos pero ≤60 minutos
                extra_hours_50 = 0.5
            # ≤30 minutos = no se abona extra

        return round(regular_hours, 2), round(extra_hours_50, 2), round(extra_hours_100, 2)

    def _calculate_saturday_extras_new_rules(self, entrada_local: datetime, salida_local: datetime,
                                           time_slots: List[Dict], has_late: bool = False) -> Tuple[float, float, float]:
        """
        NUEVAS REGLAS para sábados:
        - Trabajo de 09:00 a 13:00 = 4 horas al 100%
        - Descuentos por tardanza/retiro anticipado
        - Extras adicionales si se quedan más tiempo
        """
        if not entrada_local or not salida_local or salida_local <= entrada_local:
            return 0.0, 0.0, 0.0

        # Horario estándar sábado
        inicio_sabado = entrada_local.replace(hour=9, minute=0, second=0, microsecond=0)
        fin_sabado = entrada_local.replace(hour=13, minute=0, second=0, microsecond=0)

        # Calcular tardanza y retiro anticipado en minutos
        minutos_tardanza = max(0, (entrada_local - inicio_sabado).total_seconds() / 60.0)
        minutos_retiro_anticipado = max(0, (fin_sabado - salida_local).total_seconds() / 60.0) if salida_local < fin_sabado else 0

        # Empezar con 4 horas base al 100%
        base_hours_100 = 4.0
        
        # Descuentos por tardanza
        if minutos_tardanza > 30:
            base_hours_100 -= 1.0  # Descuenta 1 hora
        elif minutos_tardanza > 6:
            base_hours_100 -= 0.5  # Descuenta media hora

        # Descuentos por retiro anticipado
        if minutos_retiro_anticipado > 30:
            base_hours_100 -= 1.0  # Descuenta 1 hora
        elif minutos_retiro_anticipado > 6:
            base_hours_100 -= 0.5  # Descuenta media hora

        # Asegurar que no sea negativo
        base_hours_100 = max(0.0, base_hours_100)

        # Extras adicionales si se quedaron más tiempo
        extra_hours_100 = 0.0
        if salida_local > fin_sabado:
            minutos_extra = (salida_local - fin_sabado).total_seconds() / 60.0
            
            if minutos_extra > 60:  # Más de 1 hora
                extra_hours_100 = 1.0
            elif minutos_extra > 30:  # Más de 30 minutos pero menos de 1 hora
                extra_hours_100 = 0.5

        total_hours_100 = base_hours_100 + extra_hours_100

        return 0.0, 0.0, round(total_hours_100, 2)

    def calculate_compensations(self, extra_hours_50: float, extra_hours_100: float,
                                pending_hours: float) -> Dict:
        """Calcula compensaciones de horas extras con horas pendientes"""
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
        """Calcula horas nocturnas (21:00 → 05:00) en TZ Argentina."""
        if not hora_entrada or not hora_salida or hora_salida <= hora_entrada:
            return 0.0
        
        entrada_local = hora_entrada.astimezone(self.tz)
        salida_local = hora_salida.astimezone(self.tz)

        start_nocturna = entrada_local.replace(
            hour=self.hora_nocturna_inicio, minute=0, second=0, microsecond=0
        )
        end_nocturna = entrada_local.replace(
            hour=self.hora_nocturna_fin, minute=0, second=0, microsecond=0
        )
        if self.hora_nocturna_fin <= self.hora_nocturna_inicio:
            end_nocturna += timedelta(days=1)

        inicio = max(entrada_local, start_nocturna)
        fin = min(salida_local, end_nocturna)

        if fin <= inicio:
            return 0.0

        return round((fin - inicio).total_seconds() / 3600.0, 2)
    
    def get_day_of_week_spanish(self, date: datetime) -> str:
        """Nombre del día en español"""
        days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        return days[date.weekday()]

    # Métodos helpers (copiados del original)
    def _horas_interseccion(self, a1: Optional[datetime], a2: Optional[datetime],
                             b1: Optional[datetime], b2: Optional[datetime]) -> float:
        """Horas de intersección entre [a1,a2] y [b1,b2]"""
        if not a1 or not a2 or not b1 or not b2:
            return 0.0
        ini = max(a1, b1)
        fin = min(a2, b2)
        if fin <= ini:
            return 0.0
        return (fin - ini).total_seconds() / 3600.0

    def _sunday_from_times(self, entrada_local: Optional[datetime], salida_local: Optional[datetime],
                           time_slots: List[Dict]) -> Tuple[float, float]:
        """Lógica de domingo"""
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
        """
        Devuelve (entrada_local, salida_local, comienzo_hhmm, fin_hhmm) en TZ AR.
        CORREGIDO: Toma la PRIMERA entrada y la ÚLTIMA salida del día
        """
        if not entries:
            return None, None, '', ''

        # Ordenar entries por tiempo
        sorted_entries = sorted(entries, key=lambda x: x.get('time', ''))
        
        # Buscar primera entrada START y última salida END
        first_start = None
        last_end = None
        
        for entry in sorted_entries:
            if entry.get('type') == 'START' and entry.get('time'):
                if first_start is None:  # Solo tomar la primera
                    first_start = entry
            elif entry.get('type') == 'END' and entry.get('time'):
                last_end = entry  # Siempre actualizar con la última

        entrada_local: Optional[datetime] = None
        salida_local: Optional[datetime] = None
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
        """
        Calcula las horas TOTALES trabajadas sumando todos los períodos START/END
        """
        if not entries:
            return 0.0
        
        # Ordenar entries por tiempo
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
                # Calcular horas de este período
                period_hours = (dt - current_start).total_seconds() / 3600.0
                total_hours += period_hours
                current_start = None
        
        return round(total_hours, 2)

    # Método para compatibilidad con versión anterior
    def process_attendance_report(self, start_date: str, end_date: str, 
                                user_ids: List[str] = None,
                                progress_callback = None) -> Dict:
        """
        Método de compatibilidad - SIEMPRE usa formato detallado
        """
        return self.process_attendance_report_detailed(
            start_date=start_date,
            end_date=end_date, 
            user_ids=user_ids,
            progress_callback=progress_callback,
            report_type="detailed"
        )


# Funciones utilitarias para compatibilidad con código existente
def process_employee_data_from_day_summaries(day_summaries: List[Dict], employee_info: Dict, 
                                             previous_pending_hours: float = 0, 
                                             period_dates: Dict = None, holidays: List[Dict] = None) -> Dict:
    calculator = ArgentineHoursCalculatorEnhanced()
    return calculator.process_employee_data(day_summaries, employee_info, previous_pending_hours, holidays)


def calculate_compensations(extra_hours_50: float, extra_hours_100: float, pending_hours: float) -> Dict:
    calculator = ArgentineHoursCalculatorEnhanced()
    return calculator.calculate_compensations(extra_hours_50, extra_hours_100, pending_hours)


# Alias para compatibilidad
ArgentineHoursCalculator = ArgentineHoursCalculatorEnhanced