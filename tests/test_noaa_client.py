import pytest
from app.extraction.noaa_client import NOAAClient, calculate_hail_physics
from app.schemas.storm_schema import GeoJSONFeatureCollection


def test_calculate_hail_physics():
    # 2.50" hail (tennis ball size)
    p25 = calculate_hail_physics(2.50)
    assert p25["mass_grams"] > 100.0
    assert 60.0 < p25["terminal_velocity_mph"] < 90.0
    assert p25["kinetic_energy_joules"] > 40.0

    # 1.75" hail (golf ball size)
    p175 = calculate_hail_physics(1.75)
    assert p175["mass_grams"] < p25["mass_grams"]
    assert p175["kinetic_energy_joules"] < p25["kinetic_energy_joules"]

    # 0" or negative
    p0 = calculate_hail_physics(0)
    assert p0["kinetic_energy_joules"] == 0.0


def test_noaa_client_swaths():
    client = NOAAClient()
    swaths = client.get_canonical_swaths()
    assert isinstance(swaths, GeoJSONFeatureCollection)
    assert len(swaths.features) > 0

    f = swaths.features[0]
    assert f.geometry.type == "Polygon"
    assert f.properties["storm_name"] == "May 28, 2024 Dallas Severe Hail Core"
    assert f.properties["max_hail_inches"] == 2.50
    assert f.properties["kinetic_energy_joules"] > 0
    assert "coordinates" in f.geometry.model_dump()
