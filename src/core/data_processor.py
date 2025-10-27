"""
Procesador de datos principal - VERSIÓN FINAL CORREGIDA
Integra las nuevas funcionalidades para Excel detallado con reglas específicas de horas extra
CORREGIDO: Error de método get_permissions_data
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime
from core.api_client import HumanApiClient
from core.hours_calculator import ArgentineHoursCalculator
from core.excel_generator import ExcelReportGenerator
import requests


class DataProcessorEnhanced:
    """Procesador principal de datos de asistencia - VERSIÓN FINAL"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_client = HumanApiClient(api_key, base_url)
        self.hours_calculator = ArgentineHoursCalculator()
        self.excel_generator = ExcelReportGenerator()
        
        # Cache para optimizar rendimiento
        self._users_cache = None
        self._departments_cache = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5 minutos
        
        # Configurar session para permisos
        self._setup_permissions_session()
    
    def _setup_permissions_session(self):
        """Configura session para obtener permisos"""
        self._permissions_session = requests.Session()
        self._permissions_session.headers.update({
            'User-Agent': 'Python/3.9 requests'
        })
    
    def get_permissions_data(self) -> List[Dict]:
        """
        Obtiene datos de permisos desde la API de Redash con refresh automático y debugging completo
        """
        try:
            # 1. Configurar URLs y headers
            refresh_url = "https://redash.humand.co/api/queries/20036/refresh"
            results_url = "https://redash.humand.co/api/queries/20036/results"
            api_key_user = "tIuuysHOXHdN7WArCwGAFrJ9byyZrfBuY4svmMtS"
            
            headers = {
                'Authorization': api_key_user,
                'User-Agent': 'Python/3.9 requests',
                'Content-Type': 'application/json'
            }
            
            print("=" * 60)
            print("🔄 INICIANDO OBTENCIÓN DE PERMISOS")
            print("=" * 60)
            print(f"Refresh URL: {refresh_url}")
            print(f"Results URL: {results_url}")
            print(f"Headers: {headers}")
            
            # 2. Hacer refresh del query para obtener datos actualizados
            print("\n🔄 Paso 1: Haciendo refresh del query...")
            refresh_response = self._permissions_session.post(
                refresh_url, 
                headers=headers, 
                timeout=30
            )
            
            print(f"📊 Refresh response code: {refresh_response.status_code}")
            print(f"📊 Refresh response headers: {dict(refresh_response.headers)}")
            
            if refresh_response.status_code not in [200, 202]:
                print(f"⚠️ Warning: Refresh falló con código {refresh_response.status_code}")
                print(f"Response text: {refresh_response.text[:500]}...")
            else:
                print("✅ Refresh exitoso")
            
            # 3. Pequeña pausa para que el refresh se complete
            import time
            print("\n⏳ Esperando 3 segundos para que se complete el refresh...")
            time.sleep(3)
            
            # 4. Obtener los resultados actualizados
            print("\n📥 Paso 2: Obteniendo resultados actualizados...")
            print(f"GET: {results_url}")
            
            response = self._permissions_session.get(results_url, headers=headers, timeout=30)
            print(f"📊 Results response code: {response.status_code}")
            print(f"📊 Results response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            # 5. Parsear respuesta
            print("\n🔍 Paso 3: Parseando respuesta JSON...")
            data = response.json()
            print(f"📋 Keys en respuesta: {list(data.keys())}")
            
            if 'query_result' in data:
                query_result = data['query_result']
                print(f"📋 Keys en query_result: {list(query_result.keys())}")
                
                if 'data' in query_result:
                    data_section = query_result['data']
                    print(f"📋 Keys en data: {list(data_section.keys())}")
                    
                    permissions = data_section.get('rows', [])
                    print(f"✅ Encontradas {len(permissions)} filas de permisos")
                    
                    # Debug: mostrar estructura de los primeros permisos
                    if permissions and len(permissions) > 0:
                        print(f"\n📋 Estructura del primer permiso:")
                        first_permission = permissions[0]
                        print(f"Keys: {list(first_permission.keys())}")
                        print(f"Valores: {first_permission}")
                        
                        # Mostrar algunos más si hay
                        for i, perm in enumerate(permissions[:3], 1):
                            print(f"\n📋 Permiso {i}:")
                            print(f"  employeeInternalId: {perm.get('employeeInternalId', 'NO ENCONTRADO')}")
                            print(f"  yyyy: {perm.get('yyyy', 'NO ENCONTRADO')}")
                            print(f"  mm: {perm.get('mm', 'NO ENCONTRADO')}")
                            print(f"  dd: {perm.get('dd', 'NO ENCONTRADO')}")
                            print(f"  hh_inicio: {perm.get('hh_inicio', 'NO ENCONTRADO')}")
                            print(f"  mm_inicio: {perm.get('mm_inicio', 'NO ENCONTRADO')}")
                            print(f"  hh_fin: {perm.get('hh_fin', 'NO ENCONTRADO')}")
                            print(f"  mm_fin: {perm.get('mm_fin', 'NO ENCONTRADO')}")
                    else:
                        print("⚠️ No se encontraron permisos en la respuesta")
                        
                else:
                    print("❌ No se encontró 'data' en query_result")
                    permissions = []
            else:
                print("❌ No se encontró 'query_result' en la respuesta")
                permissions = []
            
            print(f"\n✅ RESULTADO FINAL: {len(permissions)} permisos obtenidos")
            print("=" * 60)
            
            return permissions
            
        except Exception as e:
            print(f"❌ Error obteniendo permisos: {str(e)}")
            import traceback
            print(f"❌ Stack trace: {traceback.format_exc()}")
            
            # Fallback: intentar obtener resultados sin refresh
            try:
                print("\n🔄 FALLBACK: Intentando obtener resultados sin refresh...")
                fallback_url = "https://redash.humand.co/api/queries/20036/results.json?api_key=tIuuysHOXHdN7WArCwGAFrJ9byyZrfBuY4svmMtS"
                print(f"Fallback URL: {fallback_url}")
                
                response = self._permissions_session.get(fallback_url, timeout=30)
                print(f"Fallback response code: {response.status_code}")
                response.raise_for_status()
                
                data = response.json()
                permissions = data.get('query_result', {}).get('data', {}).get('rows', [])
                print(f"⚡ Fallback exitoso: {len(permissions)} permisos obtenidos")
                
                if permissions:
                    print(f"📋 Primer permiso del fallback: {permissions[0]}")
                
                return permissions
                
            except Exception as fallback_error:
                print(f"❌ Fallback también falló: {str(fallback_error)}")
                return []
    def format_permission_time_range(self, permission_data: Dict) -> str:
        """
        Formatea el rango del permiso - puede ser horario (mismo día) o de días (rango)
        """
        try:
            # Verificar si es rango de días
            dd = permission_data.get('dd', '')
            mm = permission_data.get('mm', '')
            dia2 = permission_data.get('dia2', '')
            mes2 = permission_data.get('mes2', '')
            form = permission_data.get('TipoSolicitud', '')
            hora = permission_data.get('Hora', '')
            minutos = permission_data.get('Minutos', '')
            incidencia = permission_data.get('incidencia', '')
            
            # Si tiene dia2 y mes2, es un rango de días
            if dd and mm and dia2 and mes2:
                return f"desde {dd}/{mm} hasta {dia2}/{mes2} - {form}"
            
            # Si no, verificar si es rango horario (mismo día)
            
            # Fallback...
            return f"{hora}:{minutos} - {incidencia} - {form}"
        except Exception:
            return "pedido x permiso"
    
    def test_connection(self) -> tuple[bool, str]:
        """Prueba la conexión con la API"""
        return self.api_client.test_connection()
    
    def get_users_list(self, filters: Dict = None, use_cache: bool = True) -> List[Dict]:
        """Obtiene la lista de usuarios disponibles con cache"""
        if use_cache and self._is_cache_valid():
            print("Usando usuarios desde cache")
            users = self._users_cache
        else:
            print("Cargando usuarios desde API...")
            users = self.api_client.get_users(filters)
            self._update_cache(users)
        
        if filters:
            return self._apply_user_filters(users, filters)
        
        return users
    
    def process_attendance_report_detailed(self, start_date: str, end_date: str, 
                                         user_ids: List[str] = None,
                                         progress_callback: Callable = None,
                                         report_type: str = "detailed") -> Dict:
        """
        Procesa un reporte completo de asistencia con formato detallado
        Args:
            start_date: Fecha de inicio (YYYY-MM-DD)
            end_date: Fecha de fin (YYYY-MM-DD)
            user_ids: Lista opcional de IDs de usuarios
            progress_callback: Función de callback para progreso
            report_type: "detailed" para columnas expandidas, "standard" para formato anterior
        """
        try:
            if progress_callback:
                progress_callback(0, "Iniciando procesamiento detallado...")
            
            # 1. Obtener usuarios
            if progress_callback:
                progress_callback(5, "Obteniendo usuarios...")
            
            if user_ids:
                cached_users = self.get_users_list()
                filtered_users = [u for u in cached_users if u.get('employeeInternalId') in user_ids]
            else:
                filtered_users = self.get_users_list()
            
            # 2. Obtener permisos - CORREGIDO: usar self.get_permissions_data() no self.api_client
            if progress_callback:
                progress_callback(8, "Obteniendo permisos...")
            
            permissions_data = self.get_permissions_data()  # CORREGIDO
            
            # 3. Obtener day summaries (contiene entries detalladas)
            if progress_callback:
                progress_callback(10, "Obteniendo day summaries...")
            
            day_summaries = self.api_client.get_day_summaries(
                start_date, end_date,
                [u.get('employeeInternalId') for u in filtered_users]
            )
            
            if not day_summaries:
                return {
                    'success': False,
                    'error': 'No se pudieron obtener day summaries',
                    'stage': 'api_fetch'
                }
            
            if progress_callback:
                progress_callback(60, "Procesando datos de empleados...")
            
            # 4. Procesar datos de cada empleado usando day summaries
            processed_employees = {}
            
            # Agrupar day summaries por empleado
            summaries_by_employee = {}
            for summary in day_summaries:
                employee_id = summary.get('employeeId')
                if employee_id:
                    if employee_id not in summaries_by_employee:
                        summaries_by_employee[employee_id] = []
                    summaries_by_employee[employee_id].append(summary)
            
            print(f"Day summaries obtenidos: {len(day_summaries)}")
            print(f"Empleados con data: {len(summaries_by_employee)}")
            
            # Crear índice de usuarios
            users_index = {u.get('employeeInternalId'): u for u in filtered_users}
            
            total_employees = len(summaries_by_employee)
            processed_count = 0
            
            for employee_id, employee_summaries in summaries_by_employee.items():
                if progress_callback:
                    progress = 60 + int((processed_count / total_employees) * 25)
                    employee_info = users_index.get(employee_id, {})
                    employee_name = f"{employee_info.get('firstName', '')} {employee_info.get('lastName', '')}"
                    progress_callback(progress, f"Procesando {employee_name}...")
                
                # Obtener info del empleado
                employee_info = users_index.get(employee_id, {
                    'employeeInternalId': employee_id,
                    'firstName': 'Desconocido',
                    'lastName': ''
                })
                
                # Procesar datos del empleado usando day summaries
                employee_data = self.hours_calculator.process_employee_data(
                    employee_summaries, employee_info, 0, None
                )
                
                # Enriquecer con datos de permisos
                self._enrich_with_permissions(employee_data, permissions_data)
                
                processed_employees[employee_id] = employee_data
                processed_count += 1
            
            if progress_callback:
                progress_callback(90, "Generando reporte Excel detallado...")
            
            # 5. Generar reporte Excel detallado
            excel_path = self.excel_generator.generate_report(
                processed_employees, start_date, end_date
            )
            
            if progress_callback:
                progress_callback(100, "Reporte detallado completado!")
            
            # 6. Calcular estadísticas finales
            stats = self._calculate_final_stats(processed_employees)
            
            return {
                'success': True,
                'excel_path': excel_path,
                'stats': stats,
                'processed_employees': len(processed_employees),
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'report_type': report_type,
                'api_stats': {
                    'total_day_summaries': len(day_summaries),
                    'total_employees_processed': total_employees,
                    'total_permissions': len(permissions_data)
                }
            }
            
        except Exception as e:
            error_msg = f"Error en procesamiento detallado: {str(e)}"
            print(f"Error: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'stage': 'processing'
            }
    
    def _enrich_with_permissions(self, employee_data: Dict, permissions_data: List[Dict]):
        """
        Enriquece los datos del empleado con información de permisos
        """
        employee_id = employee_data['employee_info'].get('employeeInternalId')
        print(f"\n🔍 BÚSQUEDA DE PERMISOS para empleado: {employee_id}")
        print(f"📊 Total de permisos disponibles: {len(permissions_data)}")
        
        permissions_found = 0
        
        for daily_record in employee_data['daily_data']:
            date_str = daily_record['date']  # YYYY-MM-DD
            #print(f"\n📅 Buscando permiso para fecha: {date_str}")
            
            # Buscar permiso para esta fecha y empleado
            permission = self._find_permission_for_date_and_employee(
                permissions_data, employee_id, date_str
            )
            
            if permission:
                permission_text = self.format_permission_time_range(permission)
                daily_record['permission_request'] = permission_text
                permissions_found += 1
                #print(f"✅ PERMISO ENCONTRADO para {employee_id} el {date_str}: {permission_text}")
            else:
                daily_record['permission_request'] = ""
                print(f"❌ Sin permiso para {employee_id} el {date_str}")
        
        print(f"\n📊 RESUMEN: {permissions_found} permisos encontrados para {employee_id}")
    
    def _find_permission_for_date_and_employee(self, permissions_data: List[Dict], 
                                            employee_id: str, date_str: str) -> Optional[Dict]:
        """
        Busca un permiso específico para un empleado y fecha - INCLUYE RANGOS DE DÍAS
        """
        try:
            from datetime import datetime
            
            # Convertir date_str a objeto datetime
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            year, month, day = date_str.split('-')
            
            for permission in permissions_data:
                perm_employee_id = permission.get('employeeInternalId')
                
                # Solo buscar permisos del empleado correcto
                if perm_employee_id != employee_id:
                    continue
                    
                # Verificar si es rango de días
                dd = permission.get('dd', '')
                mm = permission.get('mm', '')
                dia2 = permission.get('dia2', '')
                mes2 = permission.get('mes2', '')
                
                if dd and mm and dia2 and mes2:
                    # Es un rango de días - verificar si target_date está dentro
                    try:
                        start_date = datetime(2025, int(mm), int(dd))
                        end_date = datetime(2025, int(mes2), int(dia2))
                        
                        if start_date <= target_date <= end_date:
                            print(f"🎯 RANGO MATCH: {date_str} está en rango {dd}/{mm} - {dia2}/{mes2}")
                            return permission
                    except:
                        continue
                else:
                    # Es un día específico - lógica original
                    perm_month = str(mm).zfill(2)
                    perm_day = str(dd).zfill(2)
                    
                    if perm_month == month and perm_day == day:
                        print(f"🎯 DÍA ESPECÍFICO MATCH: {date_str}")
                        return permission
            
            return None
        except Exception as e:
            print(f"❌ Error buscando permiso: {str(e)}")
            return None
    
    def _is_cache_valid(self) -> bool:
        """Verifica si el cache es válido"""
        if not self._users_cache or not self._cache_timestamp:
            return False
        
        now = datetime.now()
        cache_age = (now - self._cache_timestamp).total_seconds()
        return cache_age < self._cache_duration
    
    def _update_cache(self, users: List[Dict]):
        """Actualiza el cache de usuarios"""
        self._users_cache = users
        self._cache_timestamp = datetime.now()
        
        # Actualizar cache de departamentos
        departments = set()
        for user in users:
            if user.get('department'):
                departments.add(user['department'])
        self._departments_cache = sorted(list(departments))
    
    def _apply_user_filters(self, users: List[Dict], filters: Dict) -> List[Dict]:
        """Aplica filtros a la lista de usuarios"""
        filtered_users = []
        
        for user in users:
            matches = True
            
            # Filtrar por departamento
            if filters.get('department') and user.get('department') != filters['department']:
                matches = False
            
            # Filtrar por estado activo
            if filters.get('active_only', True) and not user.get('isActive', True):
                matches = False
            
            if matches:
                filtered_users.append(user)
        
        return filtered_users
    
    def _calculate_final_stats(self, processed_employees: Dict) -> Dict:
        """Calcula estadísticas finales del reporte"""
        if not processed_employees:
            return {
                'total_employees': 0,
                'total_hours_worked': 0,
                'total_regular_hours': 0,
                'total_extra_hours_50': 0,
                'total_extra_hours_100': 0,
                'total_night_hours': 0,
                'total_pending_hours': 0,
                'avg_hours_per_employee': 0,
                'total_entries_processed': 0,
                'employees_with_multiple_entries': 0
            }
        
        total_employees = len(processed_employees)
        total_hours_worked = sum(emp['totals']['total_hours_worked'] for emp in processed_employees.values())
        total_regular_hours = sum(emp['totals']['total_regular_hours'] for emp in processed_employees.values())
        total_extra_hours_50 = sum(emp['totals']['total_extra_hours_50'] for emp in processed_employees.values())
        total_extra_hours_100 = sum(emp['totals']['total_extra_hours_100'] for emp in processed_employees.values())
        total_night_hours = sum(emp['totals']['total_night_hours'] for emp in processed_employees.values())
        total_pending_hours = sum(emp['compensations']['remaining_pending_hours'] for emp in processed_employees.values())
        
        # Estadísticas adicionales para el reporte detallado
        total_entries = 0
        employees_with_multiple_entries = 0
        
        for employee_data in processed_employees.values():
            for daily_record in employee_data['daily_data']:
                entries_count = len(daily_record.get('raw_entries', []))
                total_entries += entries_count
                
                if entries_count > 2:  # Más de una entrada y una salida
                    employees_with_multiple_entries += 1
        
        return {
            'total_employees': total_employees,
            'total_hours_worked': round(total_hours_worked, 2),
            'total_regular_hours': round(total_regular_hours, 2),
            'total_extra_hours_50': round(total_extra_hours_50, 2),
            'total_extra_hours_100': round(total_extra_hours_100, 2),
            'total_night_hours': round(total_night_hours, 2),
            'total_pending_hours': round(total_pending_hours, 2),
            'avg_hours_per_employee': round(total_hours_worked / total_employees, 2) if total_employees > 0 else 0,
            'total_entries_processed': total_entries,
            'employees_with_multiple_entries': employees_with_multiple_entries
        }
    
    def get_available_filters(self, progress_callback: Callable = None) -> Dict:
        """Obtiene los filtros disponibles basados en los usuarios"""
        try:
            if progress_callback:
                progress_callback(20, "Obteniendo usuarios...")
            
            users = self.get_users_list()
            
            if progress_callback:
                progress_callback(60, f"Procesando {len(users)} usuarios...")
            
            # Extraer departamentos únicos
            departments = set()
            locations = set()
            job_titles = set()
            
            for user in users:
                if user.get('department'):
                    departments.add(user['department'])
                if user.get('location'):
                    locations.add(user['location'])
                if user.get('jobTitle'):
                    job_titles.add(user['jobTitle'])
            
            if progress_callback:
                progress_callback(80, "Configurando filtros...")
            
            return {
                'departments': sorted(list(departments)),
                'locations': sorted(list(locations)),
                'job_titles': sorted(list(job_titles)),
                'total_users': len(users)
            }
            
        except Exception as e:
            print(f"Error obteniendo filtros: {str(e)}")
            return {
                'departments': [],
                'locations': [],
                'job_titles': [],
                'total_users': 0
            }
    
    def validate_date_range(self, start_date: str, end_date: str) -> Dict:
        """Valida un rango de fechas"""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            errors = []
            warnings = []
            
            # Validaciones básicas
            if start_dt > end_dt:
                errors.append("La fecha de inicio debe ser anterior a la fecha de fin")
            
            # Validar que no sea muy futuro
            now = datetime.now()
            if end_dt > now:
                warnings.append("La fecha de fin es futura, algunos datos pueden no estar disponibles")
            
            # Validar que no sea muy antiguo
            min_date = datetime(2024, 1, 1)
            if start_dt < min_date:
                warnings.append("Fechas muy antiguas pueden tener datos limitados")
            
            # Validar rango no muy amplio
            diff_days = (end_dt - start_dt).days + 1
            if diff_days > 365:
                warnings.append("Rangos muy amplios pueden afectar el rendimiento")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'day_count': diff_days
            }
            
        except ValueError as e:
            return {
                'is_valid': False,
                'errors': [f"Formato de fecha inválido: {str(e)}"],
                'warnings': [],
                'day_count': 0
            }

    # Método para compatibilidad con versión anterior
    def process_attendance_report(self, start_date: str, end_date: str, 
                                user_ids: List[str] = None,
                                progress_callback: Callable = None) -> Dict:
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


# Alias para compatibilidad con código existente
DataProcessor = DataProcessorEnhanced