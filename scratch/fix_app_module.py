path = r'c:\Users\gabra\Documents\Biblioteca\biblioteca-webapp\src\app\app.module.ts'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

target = "    PrestamoSuccessModalComponent\n  ],"
replacement = "    PrestamoSuccessModalComponent,\n    UsuariosScreenComponent\n  ],"
c = c.replace(target, replacement)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('app.module.ts updated with UsuariosScreenComponent in declarations!')
