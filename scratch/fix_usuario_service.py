import os

ts_content = r"""import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Sancion {
  prestamo_id: number;
  libro_titulo: string;
  libro_autor: string;
  fecha_prestamo: string;
  fecha_vencimiento: string;
  fecha_devolucion: string;
  dias_retraso: number;
  monto_multa: number;
  multa_formateada: string;
  pagada: boolean;
  fecha_pago: string | null;
  es_rn04: boolean;
  bloqueo_hasta: string | null;
  motivo: string;
}

export interface UsuarioItem {
  id: number;
  user_id: number;
  modelo_id: number;
  tipo_modelo: string;
  email: string;
  username: string;
  nombre: string;
  apellido_paterno: string;
  apellido_materno: string;
  nombre_completo: string;
  matricula: string;
  rol: string;
  is_active: boolean;
  prestamos_activos: number;
  limite_prestamos: number;
  prestamos_display: string;
  bloqueado: boolean;
  bloqueo_motivo: string;
  bloqueo_hasta: string | null;
  estado: string;
  multas_pendientes: number;
  multas_display: string;
  sanciones: Sancion[];
  historial_prestamos?: any[];
}

@Injectable({
  providedIn: 'root'
})
export class UsuarioService {
  private apiUrl = 'http://127.0.0.1:8000';

  constructor(private http: HttpClient) {}

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem('token') || '';
    return new HttpHeaders({
      'Content-Type': 'application/json',
      'Authorization': 'Token ' + token
    });
  }

  registrarAlumno(data: any): Observable<any> {
    return this.http.post(this.apiUrl + '/alumnos/', data);
  }

  registrarAdmin(data: any): Observable<any> {
    return this.http.post(this.apiUrl + '/admin/', data);
  }

  getAlumnos(): Observable<any> {
    return this.http.get(this.apiUrl + '/lista-alumnos/');
  }

  getAdmins(): Observable<any> {
    return this.http.get(this.apiUrl + '/lista-admins/');
  }

  login(email: string, password: string): Observable<any> {
    return this.http.post(this.apiUrl + '/token/', { username: email, password: password });
  }

  // --- Gestión Integral de Usuarios (Admin) ---
  getUsuarios(): Observable<UsuarioItem[]> {
    return this.http.get<UsuarioItem[]>(this.apiUrl + '/usuarios/', { headers: this.getAuthHeaders() });
  }

  getUsuario(id: number): Observable<UsuarioItem> {
    return this.http.get<UsuarioItem>(this.apiUrl + '/usuarios/' + id + '/', { headers: this.getAuthHeaders() });
  }

  getFichaUsuario(id: number): Observable<UsuarioItem> {
    return this.http.get<UsuarioItem>(this.apiUrl + '/usuarios/' + id + '/ficha/', { headers: this.getAuthHeaders() });
  }

  crearUsuario(data: any): Observable<any> {
    return this.http.post<any>(this.apiUrl + '/usuarios/', data, { headers: this.getAuthHeaders() });
  }

  actualizarUsuario(id: number, data: any): Observable<any> {
    return this.http.put<any>(this.apiUrl + '/usuarios/' + id + '/', data, { headers: this.getAuthHeaders() });
  }

  desactivarUsuario(id: number): Observable<any> {
    return this.http.post<any>(this.apiUrl + '/usuarios/' + id + '/desactivar/', {}, { headers: this.getAuthHeaders() });
  }

  reactivarUsuario(id: number): Observable<any> {
    return this.http.post<any>(this.apiUrl + '/usuarios/' + id + '/reactivar/', {}, { headers: this.getAuthHeaders() });
  }

  pagarMulta(userId: number, prestamoId?: number): Observable<any> {
    const payload = prestamoId ? { prestamo_id: prestamoId } : {};
    return this.http.post<any>(this.apiUrl + '/usuarios/' + userId + '/pagar-multa/', payload, { headers: this.getAuthHeaders() });
  }
}
"""

path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\services\usuario.service.ts'
with open(path, 'w', encoding='utf-8') as f:
    f.write(ts_content.strip() + '\n')
print('usuario.service.ts fixed successfully!')
