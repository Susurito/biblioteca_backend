import re

path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\components\navbar\navbar.component.html'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# Replace Contáctanos to have *ngIf="!isAdmin"
new_contacto = '''        <li class="nav-item" *ngIf="!isAdmin">
          <a class="nav-link" routerLink="/contacto" routerLinkActive="active" (click)="closeNav()">
            <span class="nav-icon-badge"><i class="bi bi-envelope"></i></span>
            <span class="nav-link-text">Contáctanos</span>
          </a>
        </li>'''

# Check if there's already admin links
admin_links = '''        <!-- Pestañas para Administrador -->
        <li class="nav-item" *ngIf="isAdmin">
          <a class="nav-link" routerLink="/admin" routerLinkActive="active" id="nav-prestamos-admin"
            (click)="closeNav()">
            <span class="nav-icon-badge"><i class="bi bi-arrow-left-right"></i></span>
            <span class="nav-link-text">Préstamos</span>
          </a>
        </li>
        <li class="nav-item" *ngIf="isAdmin">
          <a class="nav-link" routerLink="/ejemplares" routerLinkActive="active" id="nav-ejemplares"
            (click)="closeNav()">
            <span class="nav-icon-badge"><i class="bi bi-journal-bookmark"></i></span>
            <span class="nav-link-text">Ejemplares</span>
          </a>
        </li>
        <li class="nav-item" *ngIf="isAdmin">
          <a class="nav-link" routerLink="/usuarios" routerLinkActive="active" id="nav-usuarios"
            (click)="closeNav()">
            <span class="nav-icon-badge"><i class="bi bi-people"></i></span>
            <span class="nav-link-text">Usuarios</span>
          </a>
        </li>'''

# Replace the contacto
pattern_contacto = r'<li class="nav-item"(?:\s+\*ngIf="[^"]*")?>\s*<a class="nav-link" routerLink="/contacto"[\s\S]*?</li>'
c = re.sub(pattern_contacto, new_contacto, c)

# Replace the existing admin links
pattern_admin = r'<!-- Pesta[\s\S]*?Ejemplares[\s\S]*?</li>\s*<!-- Pesta[\s\S]*?Pr[\s\S]*?</li>'
if re.search(pattern_admin, c):
    c = re.sub(pattern_admin, admin_links, c)
else:
    # If not found directly, let's look for whatever admin links currently exist
    pattern_alt = r'<!-- Pesta[\s\S]*?Ejemplares[\s\S]*?</li>'
    if 'id="nav-usuarios"' not in c:
        c = re.sub(pattern_alt, admin_links, c)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('navbar.component.html updated successfully!')
