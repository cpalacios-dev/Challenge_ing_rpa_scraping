"""
Test manual rápido de schemas.py — correr localmente con:
    python tests/test_schemas.py

No requiere pytest, solo valida los casos críticos a simple vista
e imprime "OK" por cada caso que se comporta como se espera.
"""
from src.extractor.schemas import (
    IndicadorFinanciero,
    EstadoExtraccion,
    NombreIndicador,
    FuenteOrigen,
)


def test_caso_exitoso_valido():
    """Un indicador exitoso debe aceptar un valor numérico real."""
    ind = IndicadorFinanciero(
        fecha_dato="22-06-2026",
        nombre_indicador=NombreIndicador.UF,
        valor=40798.57,
        fuente_origen=FuenteOrigen.BANCO_CENTRAL,
        estado_extraccion=EstadoExtraccion.EXITOSO,
    )
    assert ind.valor == 40798.57
    assert ind.estado_extraccion == EstadoExtraccion.EXITOSO
    print("OK: caso exitoso válido")


def test_exitoso_sin_valor_es_rechazado():
    """Un indicador 'exitoso' SIN valor (None) debe fallar:
    no puede decir que tuvo éxito sin reportar un número real."""
    try:
        IndicadorFinanciero(
            fecha_dato="22-06-2026",
            nombre_indicador=NombreIndicador.UF,
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar: 'exitoso' sin valor numérico")
    except ValueError:
        print("OK: estado 'exitoso' sin valor fue rechazado")


def test_exitoso_con_valor_cero_es_rechazado():
    """valor=0.0 nunca es válido para un indicador real (UF, Dólar, etc.
    siempre son positivos), aunque el estado diga 'exitoso'."""
    try:
        IndicadorFinanciero(
            fecha_dato="22-06-2026",
            nombre_indicador=NombreIndicador.UF,
            valor=0.0,
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar: 'exitoso' con valor=0.0")
    except ValueError:
        print("OK: estado 'exitoso' con valor=0.0 fue rechazado")


def test_fallido_con_valor_es_rechazado():
    """Un indicador 'fallido' o 'parcial' NO debe traer un valor numérico:
    no hay un número confiable que reportar."""
    try:
        IndicadorFinanciero(
            fecha_dato="22-06-2026",
            nombre_indicador=NombreIndicador.EURO,
            valor=1028.3,  # inconsistente a propósito
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.FALLIDO,
        )
        raise AssertionError("Debió fallar: 'fallido' con valor numérico")
    except ValueError:
        print("OK: estado 'fallido' con valor numérico fue rechazado")


def test_fallido_sin_valor_es_valido():
    """Caso correcto: 'fallido' con valor=None y mensaje_error explicando por qué."""
    ind = IndicadorFinanciero(
        fecha_dato="22-06-2026",
        nombre_indicador=NombreIndicador.EURO,
        fuente_origen=FuenteOrigen.BANCO_CENTRAL,
        estado_extraccion=EstadoExtraccion.FALLIDO,
        mensaje_error="Timeout esperando el selector",
    )
    assert ind.valor is None
    print("OK: estado 'fallido' con valor=None es aceptado correctamente")


def test_estado_parcial_sin_valor_es_valido():
    """Caso correcto: 'parcial' significa 'el dato existe pero no se pudo
    parsear con confianza', por lo tanto tampoco debe traer valor."""
    ind = IndicadorFinanciero(
        fecha_dato="22-06-2026",
        nombre_indicador=NombreIndicador.IPC,
        fuente_origen=FuenteOrigen.BANCO_CENTRAL,
        estado_extraccion=EstadoExtraccion.PARCIAL,
        mensaje_error="Formato de valor inesperado: 'N/D'",
    )
    assert ind.valor is None
    assert ind.estado_extraccion == EstadoExtraccion.PARCIAL
    print("OK: estado 'parcial' con valor=None es aceptado correctamente")


def test_fecha_invalida_rechazada():
    """fecha_dato debe ser una fecha real en formato DD-MM-YYYY,
    no cualquier string."""
    try:
        IndicadorFinanciero(
            fecha_dato="2026-06-22",  # formato incorrecto a propósito (ISO en vez de DD-MM-YYYY)
            nombre_indicador=NombreIndicador.UF,
            valor=100.0,
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar por formato de fecha inválido")
    except ValueError:
        print("OK: fecha con formato inválido fue rechazada")


def test_fecha_no_existente_rechazada():
    """31 de febrero no existe; strptime debe rechazarlo aunque el
    formato DD-MM-YYYY sea sintácticamente correcto."""
    try:
        IndicadorFinanciero(
            fecha_dato="31-02-2026",
            nombre_indicador=NombreIndicador.UF,
            valor=100.0,
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar: 31 de febrero no existe")
    except ValueError:
        print("OK: fecha calendario inválida (31-02) fue rechazada")


def test_nombre_indicador_no_catalogado_rechazado():
    """Solo se aceptan los indicadores definidos en el Enum NombreIndicador."""
    try:
        IndicadorFinanciero(
            fecha_dato="22-06-2026",
            nombre_indicador="Bitcoin",  # no está en el catálogo
            valor=100.0,
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar por indicador no catalogado")
    except ValueError:
        print("OK: indicador fuera de catálogo fue rechazado")


def test_fuente_origen_no_catalogada_rechazada():
    """Solo se aceptan las fuentes definidas en el Enum FuenteOrigen.
    Este es el caso real que se vio en logs de ejecución: registros
    históricos con fuente_origen='Banco Central de Chile (via Playwright)'
    (string libre) deben ser rechazados por el schema vigente."""
    try:
        IndicadorFinanciero(
            fecha_dato="22-06-2026",
            nombre_indicador=NombreIndicador.UF,
            valor=100.0,
            fuente_origen="Banco Central de Chile (via Playwright)",
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar por fuente_origen no catalogada")
    except ValueError:
        print("OK: fuente_origen fuera de catálogo fue rechazada")


def test_valor_negativo_rechazado():
    """Ningún indicador financiero de este catálogo puede ser negativo."""
    try:
        IndicadorFinanciero(
            fecha_dato="22-06-2026",
            nombre_indicador=NombreIndicador.UF,
            valor=-100.0,
            fuente_origen=FuenteOrigen.BANCO_CENTRAL,
            estado_extraccion=EstadoExtraccion.EXITOSO,
        )
        raise AssertionError("Debió fallar por valor negativo")
    except ValueError:
        print("OK: valor negativo fue rechazado")


if __name__ == "__main__":
    tests = [
        test_caso_exitoso_valido,
        test_exitoso_sin_valor_es_rechazado,
        test_exitoso_con_valor_cero_es_rechazado,
        test_fallido_con_valor_es_rechazado,
        test_fallido_sin_valor_es_valido,
        test_estado_parcial_sin_valor_es_valido,
        test_fecha_invalida_rechazada,
        test_fecha_no_existente_rechazada,
        test_nombre_indicador_no_catalogado_rechazado,
        test_fuente_origen_no_catalogada_rechazada,
        test_valor_negativo_rechazado,
    ]

    for test in tests:
        test()

    print(f"\nTodos los tests pasaron correctamente. ({len(tests)} casos)")
