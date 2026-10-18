import os

scss_content = '''/* ===================================================
   BiblioNexus — Pantalla de Usuarios (Admin)
   Diseño idéntico a la captura de pantalla de referencia
   =================================================== */

.usuarios-page {
  background-color: #ECECE9;
  min-height: calc(100vh - 72px);
  padding: 1.5rem 0 3.5rem;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* --- Toast de Notificación --- */
.usuarios-toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-radius: 14px;
  padding: 0.85rem 1.25rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  font-size: 0.92rem;
  font-weight: 500;
  animation: slideDown 0.3s ease-out;

  .bi {
    font-size: 1.2rem;
  }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* --- Tarjeta Principal del Panel --- */
.usuarios-card {
  background-color: #FFFFFF;
  border-radius: 22px;
  border: 1px solid #E2E8F0;
  padding: 2.25rem 2.5rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
}

@media (max-width: 768px) {
  .usuarios-card {
    padding: 1.25rem 1rem;
    border-radius: 16px;
  }
}

/* --- Encabezado del Panel --- */
.card-header-panel {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.75rem;

  .panel-eyebrow {
    display: block;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748B;
    margin-bottom: 0.25rem;
  }

  .panel-title {
    font-size: 2.25rem;
    font-weight: 800;
    color: #1E293B;
    margin: 0;
    letter-spacing: -0.02em;
    font-family: 'Cinzel', 'Merriweather', 'Georgia', serif;
  }

  .btn-nuevo-usuario {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    background-color: #282C34;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 0.92rem;
    padding: 0.55rem 1.25rem;
    border-radius: 9999px;
    border: none;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: all 0.2s ease;
    cursor: pointer;

    &:hover {
      background-color: #1E2228;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    .badge-nuevo {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background-color: #EAB308;
      color: #1E293B;
      font-size: 0.78rem;
      font-weight: 800;
      width: 20px;
      height: 20px;
      border-radius: 50%;
    }
  }
}

/* --- Barra de Pestañas de Rol --- */
.tabs-bar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  border-bottom: 1.5px solid #E2E8F0;
  margin-bottom: 1.75rem;
  padding-bottom: 0;
  overflow-x: auto;

  .tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: none;
    border: none;
    padding: 0.75rem 0.25rem;
    font-size: 0.95rem;
    font-weight: 500;
    color: #64748B;
    position: relative;
    cursor: pointer;
    white-space: nowrap;
    transition: color 0.2s ease;

    &:hover {
      color: #1E293B;
    }

    &.active {
      color: #1E293B;
      font-weight: 700;

      &::after {
        content: '';
        position: absolute;
        bottom: -1.5px;
        left: 0;
        right: 0;
        height: 2.5px;
        background-color: #1E293B;
        border-radius: 2px 2px 0 0;
      }
    }

    .tab-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background-color: #282C34;
      color: #FFFFFF;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.15rem 0.65rem;
      border-radius: 9999px;
      min-width: 24px;
    }
  }
}

/* --- Barra de Filtros --- */
.filters-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.75rem;

  .search-box {
    flex: 1;

    .input-search {
      width: 100%;
      background-color: #F8F9FA;
      border: 1.5px solid #E2E8F0;
      border-radius: 9999px;
      padding: 0.65rem 1.4rem;
      font-size: 0.92rem;
      color: #334155;
      outline: none;
      transition: all 0.2s ease;

      &::placeholder {
        color: #94A3B8;
      }

      &:focus {
        background-color: #FFFFFF;
        border-color: #64748B;
        box-shadow: 0 0 0 3px rgba(100, 116, 139, 0.1);
      }
    }
  }

  .filter-dropdown {
    width: 200px;
    flex-shrink: 0;

    .select-estado {
      width: 100%;
      background-color: #F8F9FA;
      border: 1.5px solid #E2E8F0;
      border-radius: 9999px;
      padding: 0.65rem 1.25rem;
      font-size: 0.92rem;
      color: #475569;
      outline: none;
      cursor: pointer;
      transition: all 0.2s ease;

      &:focus {
        background-color: #FFFFFF;
        border-color: #64748B;
      }
    }
  }
}

@media (max-width: 640px) {
  .filters-bar {
    flex-direction: column;

    .filter-dropdown {
      width: 100%;
    }
  }
}

/* --- Tabla de Usuarios --- */
.table-responsive {
  overflow-x: auto;
}

.usuarios-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;

  thead {
    tr {
      border-bottom: 1.5px solid #F1F5F9;

      th {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #64748B;
        padding: 0.85rem 1rem;
        white-space: nowrap;

        .badge-estado-header {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background-color: #EAB308;
          color: #1E293B;
          font-size: 0.68rem;
          font-weight: 800;
          width: 17px;
          height: 17px;
          border-radius: 50%;
          margin-left: 0.35rem;
          vertical-align: middle;
        }
      }
    }
  }

  tbody {
    tr {
      border-bottom: 1px solid #F1F5F9;
      transition: background-color 0.15s ease;

      &:hover {
        background-color: #FAFBFB;
      }

      &.row-inactive {
        opacity: 0.65;

        .user-name, .matricula-text, .rol-text, .prestamos-text {
          color: #94A3B8 !important;
        }
      }

      td {
        padding: 1.15rem 1rem;
        vertical-align: middle;
        font-size: 0.92rem;
      }
    }
  }

  /* Celdas individuales */
  .col-usuario {
    min-width: 240px;

    .user-cell {
      display: flex;
      align-items: center;
      gap: 0.85rem;
      cursor: pointer;

      &:hover .user-name {
        color: #0284C7;
      }

      .avatar-circle {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        border: 1.5px solid #475569;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.95rem;
        color: #334155;
        background-color: #FFFFFF;
        flex-shrink: 0;

        &.avatar-inactive {
          border-color: #CBD5E1;
          color: #94A3B8;
        }
      }

      .user-info {
        display: flex;
        flex-direction: column;

        .user-name {
          font-weight: 700;
          color: #1E293B;
          line-height: 1.25;
          transition: color 0.2s ease;
        }

        .user-email {
          font-size: 0.82rem;
          color: #64748B;
        }
      }
    }
  }

  .col-matricula {
    white-space: nowrap;
    .matricula-text {
      color: #334155;
      font-weight: 500;
    }
  }

  .col-rol {
    white-space: nowrap;
    .rol-text {
      color: #334155;
      font-weight: 600;
    }
  }

  .col-prestamos {
    white-space: nowrap;
    .prestamos-text {
      color: #334155;
      font-weight: 600;
    }
  }

  .col-estado {
    white-space: nowrap;
  }

  .col-acciones {
    white-space: nowrap;
    text-align: right;
  }
}

/* --- Badges de Estado tipo Pill --- */
.pill-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 1.15rem;
  border-radius: 9999px;
  font-size: 0.84rem;
  font-weight: 600;
  white-space: nowrap;

  &.pill-activo {
    background-color: #FFFFFF;
    color: #1E293B;
    border: 1.5px solid #282C34;
  }

  &.pill-bloqueado {
    background-color: #282C34;
    color: #FFFFFF;
    border: 1.5px solid #282C34;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }

  &.pill-inactivo {
    background-color: transparent;
    color: #94A3B8;
    border: 1.5px dashed #94A3B8;
  }
}

/* --- Botones de Acción tipo Pill --- */
.actions-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: flex-end;

  .btn-action {
    background-color: #FFFFFF;
    border-radius: 9999px;
    padding: 0.35rem 1.15rem;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;

    &.btn-editar {
      border: 1.5px solid #282C34;
      color: #1E293B;

      &:hover {
        background-color: #F8F9FA;
        transform: translateY(-1px);
      }
    }

    &.btn-desactivar {
      border: 1.5px dashed #282C34;
      color: #1E293B;

      &:hover {
        background-color: #FEF2F2;
        border-color: #DC2626;
        color: #DC2626;
      }
    }

    &.btn-reactivar {
      border: 1.5px solid #282C34;
      color: #1E293B;

      &:hover {
        background-color: #F0FDF4;
        border-color: #16A34A;
        color: #16A34A;
      }
    }
  }

  .btn-action-icon {
    background: none;
    border: none;
    color: #64748B;
    font-size: 1.15rem;
    padding: 0.3rem 0.5rem;
    border-radius: 50%;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      color: #1E293B;
      background-color: #F1F5F9;
    }
  }
}

/* ==============================================================
   MODALES (Ficha de Usuario, Nuevo, Editar)
   ============================================================== */
.modal-backdrop-custom {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
  z-index: 1050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  overflow-y: auto;
}

.modal-dialog-custom {
  width: 100%;
  max-width: 540px;
  margin: auto;

  &.modal-lg-custom {
    max-width: 820px;
  }
}

.modal-content-custom {
  background-color: #FFFFFF;
  border-radius: 20px;
  border: 1px solid #E2E8F0;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  animation: modalPop 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalPop {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-header-custom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid #F1F5F9;

  .modal-title-custom {
    font-size: 1.35rem;
    font-weight: 700;
    color: #1E293B;
    margin: 0;
  }

  .btn-close-modal {
    background: none;
    border: none;
    color: #94A3B8;
    font-size: 1.15rem;
    padding: 0.25rem;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.15s ease;

    &:hover {
      color: #1E293B;
      background-color: #F1F5F9;
    }
  }

  .avatar-circle-lg {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 2px solid #282C34;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1.25rem;
    color: #1E293B;
    background-color: #F8F9FA;
  }
}

.modal-body-custom {
  padding: 1.75rem 2rem;
  max-height: 75vh;
  overflow-y: auto;
}

.modal-footer-custom {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 2rem;
  border-top: 1px solid #F1F5F9;
  background-color: #F8F9FA;

  .btn-cancelar {
    background: none;
    border: 1.5px solid #CBD5E1;
    color: #475569;
    font-weight: 600;
    border-radius: 9999px;
    padding: 0.5rem 1.4rem;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      background-color: #E2E8F0;
      color: #1E293B;
    }
  }

  .btn-guardar {
    background-color: #282C34;
    color: #FFFFFF;
    font-weight: 600;
    border-radius: 9999px;
    padding: 0.5rem 1.5rem;
    border: none;
    cursor: pointer;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    transition: all 0.2s ease;

    &:hover:not(:disabled) {
      background-color: #1E2228;
      transform: translateY(-1px);
    }

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}

/* --- Métricas e Info en Ficha --- */
.info-metric-card {
  background-color: #F8F9FA;
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 1rem 1.25rem;
  height: 100%;

  &.has-debt {
    background-color: #FFFBEB;
    border-color: #FDE68A;
  }

  .metric-label {
    display: block;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: #64748B;
  }

  .metric-value {
    font-size: 1.4rem;
    font-weight: 800;
    color: #1E293B;
    margin-top: 0.25rem;
  }
}

/* --- Banner de Pago de Multas --- */
.payment-action-card {
  background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
  border: 1.5px solid #F59E0B;
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.12);

  .btn-pagar-multa {
    background-color: #1E293B;
    color: #FFFFFF;
    font-weight: 700;
    border-radius: 9999px;
    padding: 0.65rem 1.6rem;
    border: none;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    transition: all 0.2s ease;

    &:hover:not(:disabled) {
      background-color: #0F172A;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
  }
}

/* --- Tablas Secundarias en Ficha --- */
.section-container {
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  padding: 1.25rem;
  background-color: #FFFFFF;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;

    .section-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: #1E293B;
      margin: 0;
    }
  }
}

.custom-subtable {
  font-size: 0.88rem;

  thead th {
    background-color: #F8F9FA;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #64748B;
    border-bottom: 1.5px solid #E2E8F0;
    padding: 0.65rem 0.85rem;
  }

  tbody td {
    padding: 0.75rem 0.85rem;
    border-bottom: 1px solid #F1F5F9;
  }
}

/* --- Formularios Modales --- */
.form-label-custom {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  color: #334155;
  margin-bottom: 0.35rem;
}

.form-control-custom {
  width: 100%;
  background-color: #F8F9FA;
  border: 1.5px solid #E2E8F0;
  border-radius: 10px;
  padding: 0.6rem 0.95rem;
  font-size: 0.92rem;
  color: #1E293B;
  outline: none;
  transition: all 0.2s ease;

  &:focus {
    background-color: #FFFFFF;
    border-color: #64748B;
    box-shadow: 0 0 0 3px rgba(100, 116, 139, 0.1);
  }
}
'''

path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\screen\usuarios-screen\usuarios-screen.component.scss'
with open(path, 'w', encoding='utf-8') as f:
    f.write(scss_content.strip() + '\n')
print('usuarios-screen.component.scss created successfully!')
