from django.core.management.base import BaseCommand
from django.db import transaction

from biblioteca_backend.models import Libros


LIBROS = [
    {
        "titulo": "Cien años de soledad",
        "autor": "Gabriel García Márquez",
        "genero": "Realismo mágico",
        "detalles": "Novela sobre la familia Buendía y el pueblo de Macondo.",
    },
    {
        "titulo": "Don Quijote de la Mancha",
        "autor": "Miguel de Cervantes",
        "genero": "Novela clásica",
        "detalles": "Aventuras de Alonso Quijano y su escudero Sancho Panza.",
    },
    {
        "titulo": "El principito",
        "autor": "Antoine de Saint-Exupéry",
        "genero": "Literatura infantil",
        "detalles": "Relato filosófico sobre la amistad, el amor y la vida.",
    },
    {
        "titulo": "1984",
        "autor": "George Orwell",
        "genero": "Ciencia ficción",
        "detalles": "Distopía sobre la vigilancia y el control social.",
    },
    {
        "titulo": "Fahrenheit 451",
        "autor": "Ray Bradbury",
        "genero": "Ciencia ficción",
        "detalles": "Una sociedad donde los libros están prohibidos.",
    },
    {
        "titulo": "Orgullo y prejuicio",
        "autor": "Jane Austen",
        "genero": "Romance",
        "detalles": "Novela sobre las relaciones sociales y el matrimonio.",
    },
    {
        "titulo": "La sombra del viento",
        "autor": "Carlos Ruiz Zafón",
        "genero": "Misterio",
        "detalles": "Un joven descubre un libro misterioso en Barcelona.",
    },
    {
        "titulo": "Pedro Páramo",
        "autor": "Juan Rulfo",
        "genero": "Realismo mágico",
        "detalles": "Búsqueda de un padre en el pueblo de Comala.",
    },
    {
        "titulo": "El nombre de la rosa",
        "autor": "Umberto Eco",
        "genero": "Misterio histórico",
        "detalles": "Investigación de muertes ocurridas en una abadía medieval.",
    },
    {
        "titulo": "Sapiens",
        "autor": "Yuval Noah Harari",
        "genero": "Historia",
        "detalles": "Recorrido por la historia de la humanidad.",
    },
]


class Command(BaseCommand):
    help = "Inserta libros de ejemplo en la base de datos sin duplicarlos."

    @transaction.atomic
    def handle(self, *args, **options):
        insertados = 0
        existentes = 0

        for datos_libro in LIBROS:
            libro, creado = Libros.objects.get_or_create(
                titulo=datos_libro["titulo"],
                autor=datos_libro["autor"],
                defaults={
                    "genero": datos_libro["genero"],
                    "detalles": datos_libro["detalles"],
                    "disponible": True,
                },
            )

            if creado:
                insertados += 1
            else:
                existentes += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Proceso terminado: {insertados} libros insertados, "
                f"{existentes} ya existían. Total: {Libros.objects.count()}"
            )
        )
