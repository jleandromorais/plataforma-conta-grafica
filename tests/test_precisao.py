import random

from Src.common.precisao import arredondar_tarifa


def test_mesmo_arredondamento_do_desktop():
    """O desktop usa f"{x:.4f}"; o backend usa arredondar_tarifa — têm de bater."""
    rnd = random.Random(42)
    for _ in range(20_000):
        x = rnd.uniform(-5, 5)
        assert arredondar_tarifa(x) == float(f"{x:.4f}")
