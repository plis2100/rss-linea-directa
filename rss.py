import re
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin


BASE_URL = "https://www.lineadirectaaseguradora.com"

PAGINA_PRINCIPAL = (
    "https://www.lineadirectaaseguradora.com/"
    "sala-prensa/noticias"
)

ARCHIVO_RSS = "linea-directa.xml"


def limpiar_texto(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def crear_url_inicial():
    anio_actual = datetime.now(timezone.utc).year

    return (
        "https://www.lineadirectaaseguradora.com/"
        f"sala-prensa/{anio_actual}"
    )


def descargar_pagina(url):
    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=60,
    ) as respuesta:
        return respuesta.read()


def convertir_fecha(texto):
    coincidencia = re.search(
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        texto,
    )

    if not coincidencia:
        return None

    dia = int(coincidencia.group(1))
    mes = int(coincidencia.group(2))
    anio = int(coincidencia.group(3))

    try:
        return datetime(
            anio,
            mes,
            dia,
            8,
            0,
            tzinfo=timezone.utc,
        )

    except ValueError:
        return None


def extraer_descripcion(soup):
    meta_og = soup.find(
        "meta",
        attrs={"property": "og:description"},
    )

    if meta_og and meta_og.get("content"):
        descripcion = limpiar_texto(
            meta_og["content"]
        )

        if len(descripcion) >= 50:
            return descripcion[:800]

    meta_normal = soup.find(
        "meta",
        attrs={"name": "description"},
    )

    if meta_normal and meta_normal.get("content"):
        descripcion = limpiar_texto(
            meta_normal["content"]
        )

        if len(descripcion) >= 50:
            return descripcion[:800]

    principal = soup.find("main") or soup.find("article")

    if principal:
        for parrafo in principal.find_all("p"):
            texto = limpiar_texto(
                parrafo.get_text(" ", strip=True)
            )

            if len(texto) >= 80:
                return texto[:800]

    for parrafo in soup.find_all("p"):
        texto = limpiar_texto(
            parrafo.get_text(" ", strip=True)
        )

        if len(texto) >= 80:
            return texto[:800]

    return (
        "Noticia publicada por "
        "Línea Directa Aseguradora."
    )


def obtener_enlaces():
    url_pagina = crear_url_inicial()

    paginas_vistas = set()
    enlaces_vistos = set()
    enlaces_noticias = []

    for _ in range(15):
        if not url_pagina:
            break

        if url_pagina in paginas_vistas:
            break

        paginas_vistas.add(url_pagina)

        print(f"Leyendo listado: {url_pagina}")

        contenido = descargar_pagina(url_pagina)
        soup = BeautifulSoup(
            contenido,
            "html.parser",
        )

        for enlace in soup.find_all("a", href=True):
            texto_enlace = limpiar_texto(
                enlace.get_text(" ", strip=True)
            ).lower()

            if "leer más" not in texto_enlace:
                continue

            url_noticia = urljoin(
                BASE_URL,
                enlace["href"],
            )

            url_noticia = url_noticia.split("#")[0]

            if "/sala-de-prensa/-/" not in url_noticia:
                continue

            if url_noticia in enlaces_vistos:
                continue

            enlaces_vistos.add(url_noticia)
            enlaces_noticias.append(url_noticia)

        siguiente = None

        for enlace in soup.find_all("a", href=True):
            texto_enlace = limpiar_texto(
                enlace.get_text(" ", strip=True)
            ).lower()

            if texto_enlace == "siguiente":
                siguiente = urljoin(
                    BASE_URL,
                    enlace["href"],
                )
                break

        url_pagina = siguiente

    if not enlaces_noticias:
        raise RuntimeError(
            "No se encontraron noticias "
            "de Línea Directa"
        )

    return enlaces_noticias


def obtener_noticias():
    noticias = []

    for url in obtener_enlaces():
        try:
            contenido = descargar_pagina(url)

            soup = BeautifulSoup(
                contenido,
                "html.parser",
            )

            encabezado = soup.find("h1")

            if encabezado:
                titulo = limpiar_texto(
                    encabezado.get_text(
                        " ",
                        strip=True,
                    )
                )
            else:
                titulo_pagina = soup.find("title")

                if titulo_pagina:
                    titulo = limpiar_texto(
                        titulo_pagina.get_text(
                            " ",
                            strip=True,
                        )
                    )
                else:
                    print(
                        f"No se encontró título: {url}"
                    )
                    continue

            texto_pagina = limpiar_texto(
                soup.get_text(" ", strip=True)
            )

            fecha = convertir_fecha(texto_pagina)
            descripcion = extraer_descripcion(soup)

            noticias.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "descripcion": descripcion,
                }
            )

            print(f"Noticia encontrada: {titulo}")

        except Exception as error:
            print(
                f"No se pudo procesar {url}: {error}"
            )

    if not noticias:
        raise RuntimeError(
            "No se pudieron obtener noticias "
            "de Línea Directa"
        )

    fecha_minima = datetime(
        datetime.now(timezone.utc).year - 1,
        1,
        1,
        tzinfo=timezone.utc,
    )

    noticias_recientes = [
        noticia
        for noticia in noticias
        if noticia["fecha"] is None
        or noticia["fecha"] >= fecha_minima
    ]

    noticias_recientes.sort(
        key=lambda noticia: (
            noticia["fecha"]
            or datetime(
                1970,
                1,
                1,
                tzinfo=timezone.utc,
            )
        ),
        reverse=True,
    )

    return noticias_recientes[:50]


def crear_rss(noticias):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": (
                "http://www.w3.org/2005/Atom"
            ),
        },
    )

    canal = ET.SubElement(rss, "channel")

    ET.SubElement(
        canal,
        "title",
    ).text = "Línea Directa – Noticias"

    ET.SubElement(
        canal,
        "link",
    ).text = PAGINA_PRINCIPAL

    ET.SubElement(
        canal,
        "description",
    ).text = (
        "Últimas noticias oficiales de "
        "Línea Directa Aseguradora"
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "es-es"

    ET.SubElement(
        canal,
        "{http://www.w3.org/2005/Atom}link",
        {
            "href": (
                "https://raw.githubusercontent.com/"
                "plis2100/rss-linea-directa/"
                "main/linea-directa.xml"
            ),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    ahora = datetime.now(timezone.utc)

    ET.SubElement(
        canal,
        "lastBuildDate",
    ).text = format_datetime(ahora)

    ET.SubElement(
        canal,
        "ttl",
    ).text = "60"

    for noticia in noticias:
        elemento = ET.SubElement(
            canal,
            "item",
        )

        ET.SubElement(
            elemento,
            "title",
        ).text = noticia["titulo"]

        ET.SubElement(
            elemento,
            "link",
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "guid",
            {"isPermaLink": "true"},
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "description",
        ).text = noticia["descripcion"]

        ET.SubElement(
            elemento,
            "source",
            {"url": PAGINA_PRINCIPAL},
        ).text = "Línea Directa Aseguradora"

        if noticia["fecha"]:
            ET.SubElement(
                elemento,
                "pubDate",
            ).text = format_datetime(
                noticia["fecha"]
            )

    arbol = ET.ElementTree(rss)
    ET.indent(arbol, space="  ")

    arbol.write(
        ARCHIVO_RSS,
        encoding="utf-8",
        xml_declaration=True,
    )


def validar_rss():
    archivo = Path(ARCHIVO_RSS)

    if not archivo.exists():
        raise RuntimeError(
            "No se creó linea-directa.xml"
        )

    if archivo.stat().st_size < 500:
        raise RuntimeError(
            "linea-directa.xml está vacío"
        )

    raiz = ET.parse(archivo).getroot()
    elementos = raiz.findall(
        "./channel/item"
    )

    if not elementos:
        raise RuntimeError(
            "La RSS no contiene noticias"
        )

    return len(elementos)


def main():
    noticias = obtener_noticias()
    crear_rss(noticias)
    cantidad = validar_rss()

    print(
        f"RSS creada correctamente: "
        f"{cantidad} noticias"
    )

    print(
        f"Última noticia: "
        f"{noticias[0]['titulo']}"
    )

    print(
        f"Archivo generado: {ARCHIVO_RSS}"
    )


if __name__ == "__main__":
    main()
