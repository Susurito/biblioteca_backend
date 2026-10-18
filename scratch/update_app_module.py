path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\app.module.ts'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

import_stmt = "import { UsuariosScreenComponent } from './screen/usuarios-screen/usuarios-screen.component';"
if import_stmt not in c:
    target_imp = "import { EjemplaresScreenComponent } from './screen/ejemplares-screen/ejemplares-screen.component';"
    c = c.replace(target_imp, target_imp + '\n' + import_stmt)

dec_stmt = "    UsuariosScreenComponent,"
if "UsuariosScreenComponent" not in c:
    target_dec = "    EjemplaresScreenComponent,"
    c = c.replace(target_dec, target_dec + '\n' + dec_stmt)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('app.module.ts updated successfully!')
