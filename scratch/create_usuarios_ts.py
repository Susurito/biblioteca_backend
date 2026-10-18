import os

ts_content = '''import { Component, OnInit } from '@angular/core';
import { UsuarioService, UsuarioItem, Sancion } from '../../services/usuario.service';

@Component({
  selector: 'app-usuarios-screen',
  templateUrl: './usuarios-screen.component.html',
  styleUrls: ['./usuarios-screen.component.scss']
})
export class UsuariosScreenComponent implements OnInit {
  usuarios: UsuarioItem[] = [];
  cargando: boolean = false;
  notificacion: { mensaje: string; tipo: 'success' | 'danger' | 'info' } | null = null;

  // Filtros
  tabActiva: 'todos' | 'estudiantes' | 'docentes' | 'bibliotecarios' = 'todos';
  filtroTexto: string = '';
  filtroEstado: string = 'todos';

  // Modal Nuevo Usuario
  mostrarModalNuevo: boolean = false;
  nuevoUsuario = {
    nombre: '',
    apellido_paterno: '',
    apellido_materno: '',
    email: '',
    matricula: '',
    rol: 'Estudiante',
    password: ''
  };
  guardandoNuevo: boolean = false;

  // Modal Editar Usuario
  mostrarModalEditar: boolean = false;
  usuarioEditando: UsuarioItem | null = null;
  formEditar = {
    nombre: '',
    apellido_paterno: '',
    apellido_materno: '',
    email: '',
    matricula: '',
    rol: 'Estudiante',
    password: ''
  };
  guardandoEditar: boolean = false;

  // Modal Ficha de Usuario
  mostrarModalFicha: boolean = false;
  usuarioFicha: UsuarioItem | null = null;
  cargandoFicha: boolean = false;
  procesandoPago: boolean = false;

  constructor(private usuarioService: UsuarioService) {}

  ngOnInit(): void {
    this.cargarUsuarios();
  }

  cargarUsuarios(): void {
    this.cargando = true;
    this.usuarioService.getUsuarios().subscribe({
      next: (data) => {
        this.usuarios = data;
        this.cargando = false;
      },
      error: (err) => {
        this.cargando = false;
        this.mostrarToast(err?.error?.error || 'Error al cargar la lista de usuarios.', 'danger');
      }
    });
  }

  cambiarTab(tab: 'todos' | 'estudiantes' | 'docentes' | 'bibliotecarios'): void {
    this.tabActiva = tab;
  }

  get usuariosFiltrados(): UsuarioItem[] {
    return this.usuarios.filter(u => {
      // 1. Filtro por Rol / Tab
      if (this.tabActiva === 'estudiantes' && u.rol.toLowerCase() !== 'estudiante') {
        return false;
      }
      if (this.tabActiva === 'docentes' && u.rol.toLowerCase() !== 'docente') {
        return false;
      }
      if (this.tabActiva === 'bibliotecarios' && !['bibliotecario', 'administrador', 'admin'].includes(u.rol.toLowerCase())) {
        return false;
      }

      // 2. Filtro por Estado
      if (this.filtroEstado !== 'todos') {
        const estadoNorm = (u.estado || '').toLowerCase();
        if (this.filtroEstado === 'activo' && estadoNorm !== 'activo') {
          return false;
        }
        if (this.filtroEstado === 'bloqueado' && !estadoNorm.startsWith('bloqueado')) {
          return false;
        }
        if (this.filtroEstado === 'inactivo' && estadoNorm !== 'inactivo') {
          return false;
        }
      }

      // 3. Filtro por Búsqueda (nombre, matrícula o correo)
      if (this.filtroTexto.trim()) {
        const query = this.filtroTexto.toLowerCase().trim();
        const coincideNombre = (u.nombre_completo || '').toLowerCase().includes(query);
        const coincideMatricula = (u.matricula || '').toLowerCase().includes(query);
        const coincideEmail = (u.email || '').toLowerCase().includes(query);
        if (!coincideNombre && !coincideMatricula && !coincideEmail) {
          return false;
        }
      }

      return true;
    });
  }

  contarPorRol(rol: string): number {
    if (rol === 'todos') {
      return this.usuarios.length;
    }
    if (rol === 'estudiante') {
      return this.usuarios.filter(u => u.rol.toLowerCase() === 'estudiante').length;
    }
    if (rol === 'docente') {
      return this.usuarios.filter(u => u.rol.toLowerCase() === 'docente').length;
    }
    if (rol === 'bibliotecario') {
      return this.usuarios.filter(u => ['bibliotecario', 'administrador', 'admin'].includes(u.rol.toLowerCase())).length;
    }
    return 0;
  }

  // --- Modal Nuevo Usuario ---
  abrirNuevoUsuarioModal(): void {
    this.nuevoUsuario = {
      nombre: '',
      apellido_paterno: '',
      apellido_materno: '',
      email: '',
      matricula: '',
      rol: 'Estudiante',
      password: ''
    };
    this.mostrarModalNuevo = true;
  }

  cerrarNuevoUsuarioModal(): void {
    this.mostrarModalNuevo = false;
  }

  guardarNuevoUsuario(): void {
    if (!this.nuevoUsuario.nombre || !this.nuevoUsuario.matricula || !this.nuevoUsuario.email) {
      this.mostrarToast('Por favor completa todos los campos requeridos.', 'danger');
      return;
    }
    this.guardandoNuevo = true;
    this.usuarioService.crearUsuario(this.nuevoUsuario).subscribe({
      next: (res) => {
        this.guardandoNuevo = false;
        this.mostrarModalNuevo = false;
        this.mostrarToast(`Usuario ${res.nombre_completo || res.email} creado exitosamente.`, 'success');
        this.cargarUsuarios();
      },
      error: (err) => {
        this.guardandoNuevo = false;
        this.mostrarToast(err?.error?.error || 'Error al crear usuario.', 'danger');
      }
    });
  }

  // --- Modal Editar Usuario ---
  abrirEditarUsuarioModal(usuario: UsuarioItem): void {
    this.usuarioEditando = usuario;
    this.formEditar = {
      nombre: usuario.nombre || '',
      apellido_paterno: usuario.apellido_paterno || '',
      apellido_materno: usuario.apellido_materno || '',
      email: usuario.email || '',
      matricula: usuario.matricula || '',
      rol: usuario.rol || 'Estudiante',
      password: ''
    };
    this.mostrarModalEditar = true;
  }

  cerrarEditarUsuarioModal(): void {
    this.mostrarModalEditar = false;
    this.usuarioEditando = null;
  }

  guardarEditarUsuario(): void {
    if (!this.usuarioEditando) return;
    this.guardandoEditar = true;
    this.usuarioService.actualizarUsuario(this.usuarioEditando.id, this.formEditar).subscribe({
      next: (res) => {
        this.guardandoEditar = false;
        this.mostrarModalEditar = false;
        this.mostrarToast(`Usuario ${res.nombre_completo || res.email} actualizado exitosamente.`, 'success');
        this.cargarUsuarios();
      },
      error: (err) => {
        this.guardandoEditar = false;
        this.mostrarToast(err?.error?.error || 'Error al actualizar usuario.', 'danger');
      }
    });
  }

  // --- Desactivar / Reactivar ---
  desactivarUsuario(usuario: UsuarioItem): void {
    if (confirm(`¿Estás seguro de desactivar al usuario ${usuario.nombre_completo}? No podrá iniciar sesión ni solicitar libros.`)) {
      this.usuarioService.desactivarUsuario(usuario.id).subscribe({
        next: (res) => {
          this.mostrarToast(`Usuario ${usuario.nombre_completo} ha sido desactivado.`, 'info');
          this.cargarUsuarios();
        },
        error: (err) => {
          this.mostrarToast(err?.error?.error || 'Error al desactivar el usuario.', 'danger');
        }
      });
    }
  }

  reactivarUsuario(usuario: UsuarioItem): void {
    this.usuarioService.reactivarUsuario(usuario.id).subscribe({
      next: (res) => {
        this.mostrarToast(`Usuario ${usuario.nombre_completo} ha sido reactivado.`, 'success');
        this.cargarUsuarios();
      },
      error: (err) => {
        this.mostrarToast(err?.error?.error || 'Error al reactivar el usuario.', 'danger');
      }
    });
  }

  // --- Ficha de Usuario y Sanciones / Pago de Multas ---
  abrirFicha(usuario: UsuarioItem): void {
    this.cargandoFicha = true;
    this.usuarioFicha = usuario;
    this.mostrarModalFicha = true;

    this.usuarioService.getFichaUsuario(usuario.id).subscribe({
      next: (ficha) => {
        this.usuarioFicha = ficha;
        this.cargandoFicha = false;
      },
      error: (err) => {
        this.cargandoFicha = false;
        this.mostrarToast('Error al consultar la ficha del usuario.', 'danger');
      }
    });
  }

  cerrarFicha(): void {
    this.mostrarModalFicha = false;
    this.usuarioFicha = null;
  }

  registrarPagoMulta(usuarioId: number, prestamoId?: number): void {
    this.procesandoPago = true;
    this.usuarioService.pagarMulta(usuarioId, prestamoId).subscribe({
      next: (res) => {
        this.procesandoPago = false;
        this.mostrarToast(res.message || 'Pago registrado exitosamente.', 'success');
        if (this.usuarioFicha) {
          this.usuarioFicha = res.usuario;
        }
        this.cargarUsuarios();
      },
      error: (err) => {
        this.procesandoPago = false;
        this.mostrarToast(err?.error?.error || 'Error al registrar el pago de la multa.', 'danger');
      }
    });
  }

  // --- Auxiliares UI ---
  getInicial(nombre: string): string {
    if (!nombre) return 'U';
    const partes = nombre.trim().split(' ');
    // Si empieza con Dr. usar la siguiente palabra
    if (partes[0].toLowerCase().startsWith('dr') && partes.length > 1) {
      return partes[1].charAt(0).toUpperCase();
    }
    return partes[0].charAt(0).toUpperCase();
  }

  mostrarToast(mensaje: string, tipo: 'success' | 'danger' | 'info'): void {
    this.notificacion = { mensaje, tipo };
    setTimeout(() => {
      if (this.notificacion && this.notificacion.mensaje === mensaje) {
        this.notificacion = null;
      }
    }, 4500);
  }
}
'''

path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\screen\usuarios-screen\usuarios-screen.component.ts'
with open(path, 'w', encoding='utf-8') as f:
    f.write(ts_content.strip() + '\n')
print('usuarios-screen.component.ts created successfully!')
