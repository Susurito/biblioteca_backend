path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\app-routing.module.ts'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

import_stmt = "import { UsuariosScreenComponent } from './screen/usuarios-screen/usuarios-screen.component';"
if import_stmt not in c:
    c = import_stmt + '\n' + c

route_entry = "  { path: 'usuarios', component: UsuariosScreenComponent, canActivate: [AdminGuard] },"
if "path: 'usuarios'" not in c:
    target = "{ path: 'ejemplares', component: EjemplaresScreenComponent, canActivate: [AdminGuard] },"
    c = c.replace(target, target + '\n' + route_entry)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('app-routing.module.ts updated successfully!')
