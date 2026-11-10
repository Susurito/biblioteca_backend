from biblioteca_common.settings import configure
globals().update(configure('libros_service', 'catalogo', identity=False))
