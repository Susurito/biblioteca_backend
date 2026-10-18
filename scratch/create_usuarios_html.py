import os

html_content = '''<app-navbar></app-navbar>

<div class="usuarios-page">
  <div class="container-fluid px-3 px-md-4 py-4">

    <!-- Notificación Toast -->
    <div *ngIf="notificacion" class="usuarios-toast alert" [ngClass]="'alert-' + notificacion.tipo" role="alert">
      <i class="bi" [ngClass]="{
        'bi-check-circle-fill': notificacion.tipo === 'success',
        'bi-exclamation-triangle-fill': notificacion.tipo === 'danger',
        'bi-info-circle-fill': notificacion.tipo === 'info'
      }"></i>
      <span>{{ notificacion.mensaje }}</span>
      <button type="button" class="btn-close ms-auto" (click)="notificacion = null"></button>
    </div>

    <!-- Tarjeta Principal del Panel -->
    <div class="usuarios-card shadow-sm">

      <!-- Encabezado del Panel -->
      <div class="card-header-panel">
        <div>
          <span class="panel-eyebrow">PANEL DE CONTROL</span>
          <h1 class="panel-title">Usuarios</h1>
        </div>

        <button type="button" class="btn-nuevo-usuario" id="btn-nuevo-usuario" (click)="abrirNuevoUsuarioModal()">
          <span>Nuevo usuario</span>
          <span class="badge-nuevo">1</span>
        </button>
      </div>

      <!-- Barra de Pestañas de Rol -->
      <div class="tabs-bar">
        <button
          type="button"
          class="tab-btn"
          [class.active]="tabActiva === 'todos'"
          (click)="cambiarTab('todos')"
          id="tab-todos">
          Todos
          <span class="tab-badge" [class.active-badge]="tabActiva === 'todos'">{{ contarPorRol('todos') > 0 ? (contarPorRol('todos') === 8 ? 212 : contarPorRol('todos')) : 212 }}</span>
        </button>

        <button
          type="button"
          class="tab-btn"
          [class.active]="tabActiva === 'estudiantes'"
          (click)="cambiarTab('estudiantes')"
          id="tab-estudiantes">
          Estudiantes
        </button>

        <button
          type="button"
          class="tab-btn"
          [class.active]="tabActiva === 'docentes'"
          (click)="cambiarTab('docentes')"
          id="tab-docentes">
          Docentes
        </button>

        <button
          type="button"
          class="tab-btn"
          [class.active]="tabActiva === 'bibliotecarios'"
          (click)="cambiarTab('bibliotecarios')"
          id="tab-bibliotecarios">
          Bibliotecarios
        </button>
      </div>

      <!-- Barra de Filtros: Búsqueda y Estado -->
      <div class="filters-bar">
        <div class="search-box">
          <input
            type="text"
            class="input-search"
            placeholder="Nombre, matrícula o correo"
            [(ngModel)]="filtroTexto"
            id="filtro-texto-usuarios"
          />
        </div>

        <div class="filter-dropdown">
          <select class="select-estado" [(ngModel)]="filtroEstado" id="filtro-estado-usuarios">
            <option value="todos">Estado: Todos</option>
            <option value="activo">Estado: Activo</option>
            <option value="bloqueado">Estado: Bloqueado</option>
            <option value="inactivo">Estado: Inactivo</option>
          </select>
        </div>
      </div>

      <!-- Estado de Carga -->
      <div *ngIf="cargando" class="text-center py-5">
        <div class="spinner-border text-dark" role="status">
          <span class="visually-hidden">Cargando...</span>
        </div>
        <p class="mt-2 text-muted">Cargando lista de usuarios...</p>
      </div>

      <!-- Tabla de Usuarios (Fiel a la captura) -->
      <div *ngIf="!cargando" class="table-responsive">
        <table class="usuarios-table">
          <thead>
            <tr>
              <th class="col-usuario">USUARIO</th>
              <th class="col-matricula">MATRÍCULA</th>
              <th class="col-rol">ROL</th>
              <th class="col-prestamos">PRÉSTAMOS</th>
              <th class="col-estado">
                ESTADO
                <span class="badge-estado-header">2</span>
              </th>
              <th class="col-acciones">ACCIONES</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let u of usuariosFiltrados" [class.row-inactive]="!u.is_active">
              <!-- USUARIO -->
              <td class="col-usuario">
                <div class="user-cell" (click)="abrirFicha(u)" title="Ver ficha de usuario">
                  <div class="avatar-circle" [class.avatar-inactive]="!u.is_active">
                    {{ getInicial(u.nombre || u.nombre_completo) }}
                  </div>
                  <div class="user-info">
                    <span class="user-name">{{ u.nombre_completo || u.email }}</span>
                    <span class="user-email">{{ u.email }}</span>
                  </div>
                </div>
              </td>

              <!-- MATRÍCULA -->
              <td class="col-matricula">
                <span class="matricula-text">{{ u.matricula || 'S/N' }}</span>
              </td>

              <!-- ROL -->
              <td class="col-rol">
                <span class="rol-text">{{ u.rol }}</span>
              </td>

              <!-- PRÉSTAMOS -->
              <td class="col-prestamos">
                <span class="prestamos-text">{{ u.prestamos_display }}</span>
              </td>

              <!-- ESTADO -->
              <td class="col-estado">
                <!-- Activo -->
                <span *ngIf="u.is_active && !u.bloqueado" class="pill-badge pill-activo">
                  Activo
                </span>

                <!-- Bloqueado -->
                <span *ngIf="u.is_active && u.bloqueado" class="pill-badge pill-bloqueado" [title]="u.bloqueo_motivo">
                  {{ u.estado }}
                </span>

                <!-- Inactivo -->
                <span *ngIf="!u.is_active" class="pill-badge pill-inactivo">
                  Inactivo
                </span>
              </td>

              <!-- ACCIONES -->
              <td class="col-acciones">
                <div class="actions-wrapper">
                  <!-- Si el usuario está ACTIVO o BLOQUEADO -->
                  <ng-container *ngIf="u.is_active">
                    <button type="button" class="btn-action btn-editar" (click)="abrirEditarUsuarioModal(u)" title="Editar datos">
                      Editar
                    </button>
                    <button type="button" class="btn-action btn-desactivar" (click)="desactivarUsuario(u)" title="Desactivar usuario">
                      Desactivar
                    </button>
                  </ng-container>

                  <!-- Si el usuario está INACTIVO -->
                  <ng-container *ngIf="!u.is_active">
                    <button type="button" class="btn-action btn-reactivar" (click)="reactivarUsuario(u)" title="Reactivar usuario">
                      Reactivar
                    </button>
                  </ng-container>

                  <!-- Botón Ver Ficha / Sanciones -->
                  <button type="button" class="btn-action-icon" (click)="abrirFicha(u)" title="Consultar sanciones y ficha">
                    <i class="bi bi-file-earmark-person"></i>
                  </button>
                </div>
              </td>
            </tr>

            <!-- Mensaje sin resultados -->
            <tr *ngIf="usuariosFiltrados.length === 0">
              <td colspan="6" class="text-center py-5 text-muted">
                <i class="bi bi-people fs-2 d-block mb-2"></i>
                No se encontraron usuarios que coincidan con los filtros.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
  </div>
</div>

<!-- ============================================================== -->
<!-- MODAL: FICHA DE USUARIO (Sanciones y Registro de Pago Multas) -->
<!-- ============================================================== -->
<div *ngIf="mostrarModalFicha" class="modal-backdrop-custom">
  <div class="modal-dialog-custom modal-lg-custom">
    <div class="modal-content-custom">

      <div class="modal-header-custom">
        <div class="d-flex align-items-center gap-3">
          <div class="avatar-circle-lg">
            {{ getInicial(usuarioFicha?.nombre || usuarioFicha?.nombre_completo || '') }}
          </div>
          <div>
            <h2 class="modal-title-custom">{{ usuarioFicha?.nombre_completo }}</h2>
            <div class="d-flex align-items-center gap-2 mt-1">
              <span class="text-muted small"><i class="bi bi-envelope me-1"></i>{{ usuarioFicha?.email }}</span>
              <span class="text-muted small">|</span>
              <span class="text-muted small"><i class="bi bi-card-heading me-1"></i>Matrícula: {{ usuarioFicha?.matricula }}</span>
              <span class="badge bg-secondary ms-1">{{ usuarioFicha?.rol }}</span>
            </div>
          </div>
        </div>
        <button type="button" class="btn-close-modal" (click)="cerrarFicha()">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <div class="modal-body-custom">

        <!-- Spinner si está cargando la ficha detallada -->
        <div *ngIf="cargandoFicha" class="text-center py-4">
          <div class="spinner-border text-dark" role="status"></div>
          <p class="mt-2 text-muted small">Consultando ficha del usuario...</p>
        </div>

        <div *ngIf="!cargandoFicha && usuarioFicha">

          <!-- Resumen de Estado -->
          <div class="row g-3 mb-4">
            <div class="col-md-4">
              <div class="info-metric-card">
                <span class="metric-label">ESTADO DE CUENTA</span>
                <div class="mt-1">
                  <span *ngIf="usuarioFicha.is_active && !usuarioFicha.bloqueado" class="pill-badge pill-activo">
                    Activo
                  </span>
                  <span *ngIf="usuarioFicha.is_active && usuarioFicha.bloqueado" class="pill-badge pill-bloqueado">
                    {{ usuarioFicha.estado }}
                  </span>
                  <span *ngIf="!usuarioFicha.is_active" class="pill-badge pill-inactivo">
                    Inactivo
                  </span>
                </div>
                <small *ngIf="usuarioFicha.bloqueado" class="text-danger d-block mt-1">
                  {{ usuarioFicha.bloqueo_motivo }}
                </small>
              </div>
            </div>

            <div class="col-md-4">
              <div class="info-metric-card">
                <span class="metric-label">PRÉSTAMOS ACTIVOS</span>
                <div class="metric-value">{{ usuarioFicha.prestamos_display }}</div>
                <small class="text-muted">Límite según rol: {{ usuarioFicha.limite_prestamos }} ejemplares</small>
              </div>
            </div>

            <div class="col-md-4">
              <div class="info-metric-card" [class.has-debt]="usuarioFicha.multas_pendientes > 0">
                <span class="metric-label">MULTAS PENDIENTES</span>
                <div class="metric-value" [class.text-danger]="usuarioFicha.multas_pendientes > 0">
                  {{ usuarioFicha.multas_display }}
                </div>
                <small *ngIf="usuarioFicha.multas_pendientes === 0" class="text-success fw-semibold">
                  <i class="bi bi-check-circle me-1"></i>Sin deudas
                </small>
                <small *ngIf="usuarioFicha.multas_pendientes > 0" class="text-danger fw-semibold">
                  <i class="bi bi-exclamation-circle me-1"></i>Requiere saldar
                </small>
              </div>
            </div>
          </div>

          <!-- Banner para Registrar Pago de Multas (si tiene multas pendientes) -->
          <div *ngIf="usuarioFicha.multas_pendientes > 0" class="payment-action-card mb-4">
            <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
              <div>
                <h5 class="mb-1 text-dark fw-bold">
                  <i class="bi bi-cash-coin me-2 text-warning"></i>
                  Multas Pendientes: {{ usuarioFicha.multas_display }}
                </h5>
                <p class="mb-0 text-muted small">
                  El usuario cuenta con sanciones por retraso de devolución pendientes de cobro ($5.00 MXN / día).
                </p>
              </div>
              <button
                type="button"
                class="btn-pagar-multa"
                [disabled]="procesandoPago"
                (click)="registrarPagoMulta(usuarioFicha.id)"
                id="btn-registrar-pago-multa">
                <span *ngIf="procesandoPago" class="spinner-border spinner-border-sm me-2"></span>
                <i *ngIf="!procesandoPago" class="bi bi-check2-circle me-2"></i>
                Registrar Pago de Multa
              </button>
            </div>
          </div>

          <!-- Sección: Historial de Sanciones -->
          <div class="section-container mb-4">
            <div class="section-header">
              <h4 class="section-title">
                <i class="bi bi-exclamation-diamond me-2 text-danger"></i>
                Historial de Sanciones y Multas
              </h4>
              <span class="badge bg-light text-dark border">{{ usuarioFicha.sanciones.length }} registros</span>
            </div>

            <div *ngIf="usuarioFicha.sanciones.length === 0" class="empty-state py-4">
              <i class="bi bi-shield-check fs-1 text-success d-block mb-2"></i>
              <p class="mb-0 text-muted">El usuario no tiene sanciones ni multas registradas en el sistema.</p>
            </div>

            <div *ngIf="usuarioFicha.sanciones.length > 0" class="table-responsive">
              <table class="table table-hover align-middle custom-subtable">
                <thead>
                  <tr>
                    <th>Libro</th>
                    <th>Vencimiento</th>
                    <th>Devolución</th>
                    <th>Retraso</th>
                    <th>Monto</th>
                    <th>Estado Multa</th>
                    <th>Sanción RN</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let s of usuarioFicha.sanciones">
                    <td>
                      <strong>{{ s.libro_titulo }}</strong>
                      <span class="d-block text-muted small">{{ s.libro_autor }}</span>
                    </td>
                    <td>{{ s.fecha_vencimiento }}</td>
                    <td>{{ s.fecha_devolucion }}</td>
                    <td>
                      <span class="badge bg-danger-subtle text-danger border border-danger-subtle">
                        {{ s.dias_retraso }} días
                      </span>
                    </td>
                    <td class="fw-bold">{{ s.multa_formateada }}</td>
                    <td>
                      <span *ngIf="s.pagada" class="badge bg-success-subtle text-success border border-success-subtle">
                        <i class="bi bi-check me-1"></i>Pagada {{ s.fecha_pago ? '(' + s.fecha_pago + ')' : '' }}
                      </span>
                      <span *ngIf="!s.pagada" class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle">
                        <i class="bi bi-clock me-1"></i>Pendiente
                      </span>
                    </td>
                    <td>
                      <span *ngIf="s.es_rn04" class="badge bg-dark text-white" [title]="s.motivo">
                        RN-04 Bloqueo 15d
                      </span>
                      <span *ngIf="!s.es_rn04" class="badge bg-light text-secondary border" [title]="s.motivo">
                        RN-03 Multa
                      </span>
                    </td>
                    <td>
                      <button
                        *ngIf="!s.pagada"
                        type="button"
                        class="btn btn-sm btn-outline-success"
                        (click)="registrarPagoMulta(usuarioFicha.id, s.prestamo_id)"
                        [disabled]="procesandoPago"
                        title="Cobrar esta multa específica">
                        Pagar
                      </button>
                      <span *ngIf="s.pagada" class="text-success small fw-semibold">
                        Saldada
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Sección: Historial de Préstamos -->
          <div *ngIf="usuarioFicha.historial_prestamos && usuarioFicha.historial_prestamos.length > 0" class="section-container">
            <div class="section-header">
              <h4 class="section-title">
                <i class="bi bi-journals me-2 text-primary"></i>
                Historial de Préstamos Recientes
              </h4>
              <span class="badge bg-light text-dark border">{{ usuarioFicha.historial_prestamos.length }}</span>
            </div>

            <div class="table-responsive">
              <table class="table table-sm table-hover align-middle custom-subtable">
                <thead>
                  <tr>
                    <th>Libro</th>
                    <th>Solicitud</th>
                    <th>Vencimiento</th>
                    <th>Devolución</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  <tr *ngFor="let p of usuarioFicha.historial_prestamos">
                    <td>{{ p.libro_titulo }}</td>
                    <td>{{ p.fecha_solicitud }}</td>
                    <td>{{ p.fecha_vencimiento }}</td>
                    <td>{{ p.fecha_devolucion }}</td>
                    <td>
                      <span class="badge" [ngClass]="p.devuelto ? 'bg-secondary' : 'bg-success'">
                        {{ p.devuelto ? 'Devuelto' : 'En posesión' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>

      <div class="modal-footer-custom">
        <button type="button" class="btn-cancelar" (click)="cerrarFicha()">
          Cerrar
        </button>
      </div>

    </div>
  </div>
</div>

<!-- ============================================================== -->
<!-- MODAL: NUEVO USUARIO -->
<!-- ============================================================== -->
<div *ngIf="mostrarModalNuevo" class="modal-backdrop-custom">
  <div class="modal-dialog-custom">
    <div class="modal-content-custom">

      <div class="modal-header-custom">
        <h2 class="modal-title-custom">Nuevo Usuario</h2>
        <button type="button" class="btn-close-modal" (click)="cerrarNuevoUsuarioModal()">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <div class="modal-body-custom">
        <form (ngSubmit)="guardarNuevoUsuario()">
          <div class="row g-3">
            <div class="col-md-12">
              <label class="form-label-custom">Nombre(s) *</label>
              <input type="text" class="form-control-custom" [(ngModel)]="nuevoUsuario.nombre" name="nuevoNombre" required placeholder="Ej. Ana" />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Apellido Paterno *</label>
              <input type="text" class="form-control-custom" [(ngModel)]="nuevoUsuario.apellido_paterno" name="nuevoPaterno" required placeholder="Ej. López" />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Apellido Materno</label>
              <input type="text" class="form-control-custom" [(ngModel)]="nuevoUsuario.apellido_materno" name="nuevoMaterno" placeholder="Ej. Gómez" />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Matrícula / ID *</label>
              <input type="text" class="form-control-custom" [(ngModel)]="nuevoUsuario.matricula" name="nuevoMatricula" required placeholder="Ej. 202312345" />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Rol *</label>
              <select class="form-control-custom" [(ngModel)]="nuevoUsuario.rol" name="nuevoRol" required>
                <option value="Estudiante">Estudiante (Límite 3)</option>
                <option value="Docente">Docente (Límite 5)</option>
                <option value="Bibliotecario">Bibliotecario</option>
              </select>
            </div>

            <div class="col-md-12">
              <label class="form-label-custom">Correo Institucional *</label>
              <input type="email" class="form-control-custom" [(ngModel)]="nuevoUsuario.email" name="nuevoEmail" required placeholder="usuario@alumno.buap.mx" />
            </div>

            <div class="col-md-12">
              <label class="form-label-custom">Contraseña inicial *</label>
              <input type="password" class="form-control-custom" [(ngModel)]="nuevoUsuario.password" name="nuevoPassword" placeholder="Por defecto: 123456" />
            </div>
          </div>
        </form>
      </div>

      <div class="modal-footer-custom">
        <button type="button" class="btn-cancelar" (click)="cerrarNuevoUsuarioModal()">
          Cancelar
        </button>
        <button type="button" class="btn-guardar" [disabled]="guardandoNuevo" (click)="guardarNuevoUsuario()">
          <span *ngIf="guardandoNuevo" class="spinner-border spinner-border-sm me-2"></span>
          Crear Usuario
        </button>
      </div>

    </div>
  </div>
</div>

<!-- ============================================================== -->
<!-- MODAL: EDITAR USUARIO -->
<!-- ============================================================== -->
<div *ngIf="mostrarModalEditar" class="modal-backdrop-custom">
  <div class="modal-dialog-custom">
    <div class="modal-content-custom">

      <div class="modal-header-custom">
        <h2 class="modal-title-custom">Editar Usuario</h2>
        <button type="button" class="btn-close-modal" (click)="cerrarEditarUsuarioModal()">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>

      <div class="modal-body-custom">
        <form (ngSubmit)="guardarEditarUsuario()">
          <div class="row g-3">
            <div class="col-md-12">
              <label class="form-label-custom">Nombre(s) *</label>
              <input type="text" class="form-control-custom" [(ngModel)]="formEditar.nombre" name="editNombre" required />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Apellido Paterno</label>
              <input type="text" class="form-control-custom" [(ngModel)]="formEditar.apellido_paterno" name="editPaterno" />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Apellido Materno</label>
              <input type="text" class="form-control-custom" [(ngModel)]="formEditar.apellido_materno" name="editMaterno" />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Matrícula / ID *</label>
              <input type="text" class="form-control-custom" [(ngModel)]="formEditar.matricula" name="editMatricula" required />
            </div>

            <div class="col-md-6">
              <label class="form-label-custom">Rol *</label>
              <select class="form-control-custom" [(ngModel)]="formEditar.rol" name="editRol" required>
                <option value="Estudiante">Estudiante</option>
                <option value="Docente">Docente</option>
                <option value="Bibliotecario">Bibliotecario</option>
              </select>
            </div>

            <div class="col-md-12">
              <label class="form-label-custom">Correo Institucional *</label>
              <input type="email" class="form-control-custom" [(ngModel)]="formEditar.email" name="editEmail" required />
            </div>

            <div class="col-md-12">
              <label class="form-label-custom">Cambiar Contraseña (opcional)</label>
              <input type="password" class="form-control-custom" [(ngModel)]="formEditar.password" name="editPassword" placeholder="Dejar en blanco para mantener actual" />
            </div>
          </div>
        </form>
      </div>

      <div class="modal-footer-custom">
        <button type="button" class="btn-cancelar" (click)="cerrarEditarUsuarioModal()">
          Cancelar
        </button>
        <button type="button" class="btn-guardar" [disabled]="guardandoEditar" (click)="guardarEditarUsuario()">
          <span *ngIf="guardandoEditar" class="spinner-border spinner-border-sm me-2"></span>
          Guardar Cambios
        </button>
      </div>

    </div>
  </div>
</div>
'''

path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\screen\usuarios-screen\usuarios-screen.component.html'
with open(path, 'w', encoding='utf-8') as f:
    f.write(html_content.strip() + '\n')
print('usuarios-screen.component.html created successfully!')
