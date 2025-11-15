"""
Unit tests for search query normalization in Neo4jProductSearch

Tests the _normalize_search_query() method which standardizes measurement units
in user queries before Lucene search.
"""

import pytest
from app.services.neo4j.product_search import Neo4jProductSearch


@pytest.mark.unit
class TestSearchQueryNormalization:
    """Test search query normalization logic"""

    @pytest.fixture
    def product_search(self, mock_neo4j_driver):
        """Product search service with mocked driver"""
        return Neo4jProductSearch(mock_neo4j_driver)

    def test_amperage_normalization(self, product_search):
        """Test amperage unit normalization - A, Amps, Ampere, Ampères"""
        # Test basic format: "500A" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500A")

        # Test with space: "500 Amps" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500 Amps")

        # Test singular: "500 Amp" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500 Amp")

        # Test full word: "500 Ampere" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500 Ampere")

        # Test plural: "500 Amperes" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500 Amperes")

        # Test French: "500 Ampères" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500 Ampères")

        # Test case insensitivity
        assert "500 A" in product_search._normalize_search_query("500 AMPS")
        assert "500 A" in product_search._normalize_search_query("500 amps")

    def test_voltage_normalization(self, product_search):
        """Test voltage unit normalization - V, Volts, Voltios"""
        # Test basic format: "380V" → "380 V"
        assert "380 V" in product_search._normalize_search_query("380V")

        # Test with space: "380 Volts" → "380 V"
        assert "380 V" in product_search._normalize_search_query("380 Volts")

        # Test singular: "380 Volt" → "380 V"
        assert "380 V" in product_search._normalize_search_query("380 Volt")

        # Test Spanish: "380 Voltios" → "380 V"
        assert "380 V" in product_search._normalize_search_query("380 Voltios")

        # Test case insensitivity
        assert "460 V" in product_search._normalize_search_query("460 volts")
        assert "460 V" in product_search._normalize_search_query("460 VOLTS")

    def test_length_meters_normalization(self, product_search):
        """Test length (meters) normalization - m, meters, metres"""
        # Test basic format: "15m" → "15 m"
        assert "15 m" in product_search._normalize_search_query("15m")

        # Test with space: "15 meters" → "15 m"
        assert "15 m" in product_search._normalize_search_query("15 meters")

        # Test singular: "5 meter" → "5 m"
        assert "5 m" in product_search._normalize_search_query("5 meter")

        # Test British spelling: "20 metres" → "20 m"
        assert "20 m" in product_search._normalize_search_query("20 metres")

        # Test case insensitivity
        assert "10 m" in product_search._normalize_search_query("10 METERS")

    def test_length_millimeters_normalization(self, product_search):
        """Test length (millimeters) normalization - mm, millimeters"""
        # Test basic format: "30mm" → "30 mm"
        assert "30 mm" in product_search._normalize_search_query("30mm")

        # Test with space: "30 millimeters" → "30 mm"
        assert "30 mm" in product_search._normalize_search_query("30 millimeters")

        # Test decimal: "1.2 millimeters" → "1.2 mm"
        assert "1.2 mm" in product_search._normalize_search_query("1.2 millimeters")

        # Test British spelling: "2 millimetres" → "2 mm"
        assert "2 mm" in product_search._normalize_search_query("2 millimetres")

        # Test case insensitivity
        assert "8 mm" in product_search._normalize_search_query("8 MILLIMETERS")

    def test_power_watts_normalization(self, product_search):
        """Test power (Watts) normalization - W, Watts"""
        # Test basic format: "500W" → "500 W"
        assert "500 W" in product_search._normalize_search_query("500W")

        # Test with space: "500 Watts" → "500 W"
        assert "500 W" in product_search._normalize_search_query("500 Watts")

        # Test singular: "500 Watt" → "500 W"
        assert "500 W" in product_search._normalize_search_query("500 Watt")

        # Test case insensitivity
        assert "400 W" in product_search._normalize_search_query("400 watts")

    def test_power_kilowatts_normalization(self, product_search):
        """Test power (kilowatts) normalization - kW, kilowatts"""
        # Test basic format: "4kW" → "4 kW"
        assert "4 kW" in product_search._normalize_search_query("4kW")

        # Test with space: "4 kilowatts" → "4 kW"
        assert "4 kW" in product_search._normalize_search_query("4 kilowatts")

        # Test singular: "4 kilowatt" → "4 kW"
        assert "4 kW" in product_search._normalize_search_query("4 kilowatt")

        # Test case insensitivity
        assert "3 kW" in product_search._normalize_search_query("3 KILOWATTS")

    def test_pressure_normalization(self, product_search):
        """Test pressure (bar) normalization"""
        # Test basic format: "5bar" → "5 bar"
        assert "5 bar" in product_search._normalize_search_query("5bar")

        # Test case insensitivity: "5 Bar" → "5 bar"
        assert "5 bar" in product_search._normalize_search_query("5 Bar")

        # Test uppercase: "5 BAR" → "5 bar"
        assert "5 bar" in product_search._normalize_search_query("5 BAR")

    def test_flow_rate_normalization(self, product_search):
        """Test flow rate normalization - l/minute, l/min, lpm"""
        # Test l/min: "7 l/min" → "7 l/minute"
        assert "7 l/minute" in product_search._normalize_search_query("7 l/min")

        # Test lpm: "7 lpm" → "7 l/minute"
        assert "7 l/minute" in product_search._normalize_search_query("7 lpm")

        # Test full: "7 liters/minute" → "7 l/minute"
        assert "7 l/minute" in product_search._normalize_search_query("7 liters/minute")

        # Test variant: "7 liter/min" → "7 l/minute"
        assert "7 l/minute" in product_search._normalize_search_query("7 liter/min")

    def test_phase_normalization(self, product_search):
        """Test phase normalization - ph, phase"""
        # Test compact: "3ph" → "3 phase"
        assert "3 phase" in product_search._normalize_search_query("3ph")

        # Test hyphenated: "1-phase" → "1 phase"
        assert "1 phase" in product_search._normalize_search_query("1-phase")

        # Test case insensitivity
        assert "3 phase" in product_search._normalize_search_query("3PH")

    def test_inches_normalization(self, product_search):
        """Test inches normalization"""
        # Test inches: "32 inches" → "32 inch"
        assert "32 inch" in product_search._normalize_search_query("32 inches")

        # Test singular: "32 inch" → "32 inch" (no change)
        assert "32 inch" in product_search._normalize_search_query("32 inch")

        # Test symbol: '32"' → "32 inch"
        result = product_search._normalize_search_query('32"')
        assert "32 inch" in result

    def test_combined_normalization(self, product_search):
        """Test multiple units in one query"""
        query = "I need a 500 Amps MIG welder with 380 Volts and 30mm wire"
        result = product_search._normalize_search_query(query)

        # All three should be normalized
        assert "500 A" in result
        assert "380 V" in result
        assert "30 mm" in result

        # Original text preserved
        assert "MIG welder" in result

    def test_no_normalization_needed(self, product_search):
        """Test query that doesn't need normalization"""
        query = "MIG welder for aluminum"
        result = product_search._normalize_search_query(query)

        # Should remain unchanged
        assert result == query

    def test_already_normalized_query(self, product_search):
        """Test query already in normalized format"""
        query = "500 A MIG welder 380 V"
        result = product_search._normalize_search_query(query)

        # Should remain unchanged (idempotent)
        assert result == query

    def test_duty_cycle_preserved(self, product_search):
        """Test duty cycle percentages are preserved as-is"""
        # Basic percent
        query = "500A at 60%"
        result = product_search._normalize_search_query(query)
        assert "60%" in result  # Percentage preserved
        assert "500 A" in result  # Amperage normalized

        # With @ symbol
        query2 = "500A @100%"
        result2 = product_search._normalize_search_query(query2)
        assert "100%" in result2

    def test_case_insensitivity(self, product_search):
        """Test all normalizations are case-insensitive"""
        # Uppercase variations
        assert "500 A" in product_search._normalize_search_query("500 AMPS")
        assert "380 V" in product_search._normalize_search_query("380 VOLTS")
        assert "15 m" in product_search._normalize_search_query("15 METERS")

        # Mixed case variations
        assert "500 A" in product_search._normalize_search_query("500 AmPs")
        assert "380 V" in product_search._normalize_search_query("380 VoLtS")

    def test_whitespace_handling(self, product_search):
        """Test normalization handles various whitespace patterns"""
        # No space: "500A" → "500 A"
        assert "500 A" in product_search._normalize_search_query("500A")

        # Extra spaces: "500    Amps" → "500 A"
        result = product_search._normalize_search_query("500    Amps")
        assert "500 A" in result

        # Leading/trailing whitespace
        result = product_search._normalize_search_query("  500 Amps  ")
        assert result.strip() == "500 A"

    def test_real_world_queries(self, product_search):
        """Test real-world query examples from data analysis"""
        # Query 1: Power source search
        query1 = "I need a 500 Amperes MIG welder for aluminum"
        result1 = product_search._normalize_search_query(query1)
        assert "500 A" in result1
        assert "aluminum" in result1

        # Query 2: Voltage and current
        query2 = "380-460 Volts power source with 400 Amps output"
        result2 = product_search._normalize_search_query(query2)
        assert "380" in result2  # Voltage range preserved
        assert "460 V" in result2
        assert "400 A" in result2

        # Query 3: Multiple specifications
        query3 = "Water-cooled feeder for 2 millimeters wire at 60%"
        result3 = product_search._normalize_search_query(query3)
        assert "2 mm" in result3
        assert "60%" in result3
        assert "Water-cooled" in result3

        # Query 4: Compact format
        query4 = "Aristo 500ix with 380V and 15m cable"
        result4 = product_search._normalize_search_query(query4)
        assert "380 V" in result4
        assert "15 m" in result4
        assert "Aristo 500ix" in result4  # Product name preserved
