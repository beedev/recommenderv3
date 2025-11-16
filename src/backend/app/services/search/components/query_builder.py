"""
Neo4j Cypher Query Builder

Centralizes all Cypher query construction logic for component searches.
Eliminates duplication by providing reusable query building methods.
"""

import logging
import re
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

logger = logging.getLogger(__name__)

# Stop words to remove from search queries for better Lucene matching
# Nov 15, 2024: Imported from old product_search.py pattern
STOP_WORDS = {
    'i', 'need', 'want', 'looking', 'for', 'a', 'an', 'the', 'is', 'am',
    'are', 'do', 'does', 'can', 'could', 'would', 'should', 'my', 'me',
    'we', 'our', 'us', 'show', 'find', 'get', 'give', 'have', 'has', 'had',
    'with', 'without', 'please', 'thanks', 'thank', 'you', 'like', 'this', 'that'
}


class Neo4jQueryBuilder:
    """
    Builds Neo4j Cypher queries for component searches.

    Responsibilities:
    - Build base MATCH clauses for component types
    - Add compatibility filters based on dependencies
    - Add search term filters from master_parameters
    - Build Lucene full-text search queries
    - Add pagination (SKIP/LIMIT clauses)
    - Normalize parameter values using parameter_normalizations.json
    """

    def __init__(self, component_config: Dict[str, Any]):
        """
        Initialize query builder with component configuration.

        Args:
            component_config: Component metadata from component_types.json
        """
        self.component_config = component_config

        # Load parameter normalization mappings
        normalizations_path = Path(__file__).parent.parent.parent / "config" / "parameter_normalizations.json"
        try:
            with open(normalizations_path, "r") as f:
                normalizations_data = json.load(f)
                self.normalizations = normalizations_data.get("normalizations", {})
                self.component_parameter_mapping = normalizations_data.get("component_parameter_mapping", {})
                logger.info(f"Loaded {len(self.normalizations)} parameter normalization types")
        except Exception as e:
            logger.warning(f"Failed to load parameter_normalizations.json: {e}")
            self.normalizations = {}
            self.component_parameter_mapping = {}

    def build_base_query(
        self,
        component_type: str,
        node_alias: str = "p"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build base MATCH clause for component type.

        Args:
            component_type: Type of component (e.g., "power_source", "feeder")
            node_alias: Neo4j node alias (default: "p")

        Returns:
            Tuple of (query_string, params_dict)

        Example:
            >>> query, params = builder.build_base_query("power_source", "ps")
            >>> # Returns: ("MATCH (ps:PowerSource)", {})
        """
        config = self.component_config.get(component_type)
        if not config:
            raise ValueError(f"Unknown component type: {component_type}")

        neo4j_label = config["neo4j_label"]
        category = config["category"]

        query = f"MATCH ({node_alias}:{neo4j_label})"
        params = {}

        # Add category filter if needed
        if category:
            query += f"\nWHERE {node_alias}.category = $category"
            params["category"] = category

        logger.debug(f"Built base query for {component_type}: {query}")
        return query, params

    def add_compatibility_filters(
        self,
        query: str,
        params: Dict[str, Any],
        component_type: str,
        selected_components: Dict[str, Any],
        node_alias: str = "target"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Add COMPATIBLE_WITH relationship filters for dependent components.

        Args:
            query: Existing query string
            params: Existing parameters dict
            component_type: Type of component being searched
            selected_components: Already selected components (ResponseJSON)
            node_alias: Alias for the target node

        Returns:
            Tuple of (updated_query, updated_params)

        Example:
            For feeder search with selected power_source:
            >>> query = "MATCH (target:Feeder)"
            >>> query, params = builder.add_compatibility_filters(
            ...     query, {}, "feeder", {"PowerSource": selected_ps}, "target"
            ... )
            >>> # Adds: MATCH (ps:PowerSource {gin: $ps_gin})
            >>> #       MATCH (target)-[:COMPATIBLE_WITH]->(ps)
        """
        config = self.component_config.get(component_type)
        if not config or not config.get("requires_compatibility"):
            return query, params

        dependencies = config.get("dependencies", [])
        if not dependencies:
            return query, params

        compatibility_clauses = []

        for dep in dependencies:
            # Map dependency key to ResponseJSON key
            dep_key_map = {
                "power_source": "PowerSource",
                "feeder": "Feeder",
                "cooler": "Cooler"
            }
            response_key = dep_key_map.get(dep)

            if not response_key or response_key not in selected_components:
                continue

            selected = selected_components[response_key]
            if not selected:
                continue

            # Get GIN from selected component
            gin = selected.get("gin") if isinstance(selected, dict) else getattr(selected, "gin", None)
            if not gin:
                continue

            # Get dependency config
            dep_config = self.component_config.get(dep)
            if not dep_config:
                continue

            dep_label = dep_config["neo4j_label"]
            dep_alias = f"{dep[:2]}_dep"  # e.g., "po_dep" for power_source

            param_name = f"{dep}_gin"
            params[param_name] = gin

            # Add MATCH clause for dependency
            compatibility_clauses.append(
                f"MATCH ({dep_alias}:{dep_label} {{gin: ${param_name}}})"
            )

            # Add COMPATIBLE_WITH relationship
            compatibility_clauses.append(
                f"MATCH ({node_alias})-[:COMPATIBLE_WITH]->({dep_alias})"
            )

            logger.info(f"Added compatibility filter: {component_type} -> {dep} (GIN: {gin})")

        if compatibility_clauses:
            query = "\n".join([query] + compatibility_clauses)

        return query, params

    def add_search_term_filters(
        self,
        query: str,
        params: Dict[str, Any],
        search_terms_dict: Dict[str, Any],
        node_alias: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Add dynamic WHERE/AND search-term filters to Cypher query.

        USER REQUIREMENT (from previous implementation):
        "If product_name has value - match on item_name using CONTAINS.
         For all features, use CONTAINS on clean_description or attribute_ruleset."

        Args:
            query: Existing query string
            params: Existing parameters dict
            search_terms_dict: Dict with "product_name" and "feature_terms" keys
            node_alias: Neo4j node alias

        Returns:
            Tuple of (updated_query, updated_params)
        """
        product_name = search_terms_dict.get("product_name")
        feature_terms = search_terms_dict.get("feature_terms", [])

        if not product_name and not feature_terms:
            return query, params

        conditions = []

        # 1. If product_name exists: Match on item_name using CONTAINS (space-insensitive)
        if product_name:
            param_name = "product_name_filter"
            conditions.append(
                f"replace(toLower({node_alias}.item_name), ' ', '') CONTAINS replace(toLower(${param_name}), ' ', '')"
            )
            params[param_name] = product_name
            logger.info(f"Added space-insensitive item_name filter for product_name: '{product_name}'")

        # 2. For all feature terms: Match on clean_description or attribute_ruleset using CONTAINS
        if feature_terms:
            for idx, term in enumerate(feature_terms):
                param_name = f"feature_{idx}"
                conditions.append(
                    f"(toLower({node_alias}.clean_description) CONTAINS toLower(${param_name}) "
                    f"OR toLower({node_alias}.attribute_ruleset) CONTAINS toLower(${param_name}))"
                )
                params[param_name] = term

            logger.info(f"Added {len(feature_terms)} feature filters on clean_description/attribute_ruleset")

        if conditions:
            query_stripped = query.strip()
            if "WHERE" in query_stripped.upper():
                query += " AND (" + " OR ".join(conditions) + ")"
            else:
                query += " WHERE (" + " OR ".join(conditions) + ")"

        return query, params

    def add_pagination(
        self,
        query: str,
        params: Dict[str, Any],
        offset: int = 0,
        limit: int = 10
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Add SKIP and LIMIT clauses for pagination.

        Args:
            query: Existing query string
            params: Existing parameters dict
            offset: Number of results to skip
            limit: Maximum results to return

        Returns:
            Tuple of (updated_query, updated_params)
        """
        params["skip"] = offset
        params["limit"] = limit

        query += "\nSKIP $skip LIMIT $limit"

        return query, params

    def add_priority_ordering(
        self,
        query: str,
        node_alias: str = "p",
        relationship_alias: str = "r"
    ) -> str:
        """
        Add ORDER BY clause for priority-based ranking.

        Args:
            query: Existing query string
            node_alias: Alias for the product node
            relationship_alias: Alias for the relationship (if exists)

        Returns:
            Updated query string
        """
        # Check if query has relationship with priority
        if "COMPATIBLE_WITH" in query and relationship_alias in query:
            query += f"\nORDER BY MIN({relationship_alias}.priority), {node_alias}.item_name"
        else:
            query += f"\nORDER BY {node_alias}.item_name"

        return query

    def build_lucene_query(
        self,
        component_type: str,
        user_message: str,
        node_alias: str = "p"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build Lucene full-text search query for component type.

        Uses OLD PRODUCT_SEARCH PATTERN:
        1. Remove stop words ("I", "need", "want", etc.)
        2. Normalize text (units, spaces)
        3. Build UNION query:
           - Query 1: Normalized text (better precision)
           - Query 2: Stop-words-removed text (better recall)
        4. Combine results with DISTINCT and order by score DESC

        Args:
            component_type: Type of component
            user_message: User's search message
            node_alias: Neo4j node alias

        Returns:
            Tuple of (query_string, params_dict)

        Example:
            >>> query, params = builder.build_lucene_query(
            ...     "power_source", "I need a 500A MIG welder", "p"
            ... )
            >>> # Returns UNION query searching both:
            >>> # - Normalized: "500A MIG welder"
            >>> # - Original: "500A MIG welder" (stop words removed)
        """
        config = self.component_config.get(component_type)
        if not config:
            raise ValueError(f"Unknown component type: {component_type}")

        if not config.get("lucene_enabled"):
            raise ValueError(f"Lucene search not enabled for {component_type}")

        neo4j_label = config["neo4j_label"]
        category = config["category"]

        # 🔧 ENHANCEMENT (Nov 15, 2024): Multi-step query processing from old product_search.py
        # Step 1: Remove stop words
        stopwords_removed = self._remove_stopwords(user_message)
        logger.info(f"Step 1 - Stopwords removed: '{user_message}' → '{stopwords_removed}'")

        # Step 2: Normalize text (units, spaces, etc.)
        normalized_text = self._normalize_search_text(stopwords_removed)
        logger.info(f"Step 2 - Normalized: '{stopwords_removed}' → '{normalized_text}'")

        # Step 3: Escape Lucene special characters
        escaped_normalized = self._escape_lucene_special_chars(normalized_text)
        escaped_stopwords = self._escape_lucene_special_chars(stopwords_removed)

        # Step 4: Build UNION query if normalized differs from stopwords-removed
        # This provides better recall by searching both versions
        if normalized_text != stopwords_removed:
            logger.info(f"Building UNION query: normalized vs stopwords-removed")

            # Neo4j 5.x requires UNION queries to be wrapped in CALL subquery
            # with each part having its own RETURN clause
            query = f"""
            CALL {{
                CALL db.index.fulltext.queryNodes('productIndex', $normalized_text)
                YIELD node AS {node_alias}, score
                WITH *
                WHERE {node_alias}:{neo4j_label}
            """
            if category:
                query += f" AND {node_alias}.category = $category"

            query += f"""
                RETURN {node_alias}, score
                UNION
                CALL db.index.fulltext.queryNodes('productIndex', $stopwords_text)
                YIELD node AS {node_alias}, score
                WITH *
                WHERE {node_alias}:{neo4j_label}
            """
            if category:
                query += f" AND {node_alias}.category = $category"

            query += f"""
                RETURN {node_alias}, score
            }}
            """

            params = {
                "normalized_text": escaped_normalized,
                "stopwords_text": escaped_stopwords,
                "category": category
            }
        else:
            # Single query when no normalization happened
            logger.info(f"Building single query: '{stopwords_removed}'")

            query = f"""
            CALL db.index.fulltext.queryNodes('productIndex', $search_text)
            YIELD node AS {node_alias}, score
            WITH *
            WHERE {node_alias}:{neo4j_label}
            """
            if category:
                query += f" AND {node_alias}.category = $category"

            params = {
                "search_text": escaped_stopwords,
                "category": category
            }

        logger.debug(f"Built Lucene query for {component_type}")
        return query, params

    def build_return_clause(
        self,
        node_alias: str = "p",
        include_score: bool = False,
        relationship_alias: Optional[str] = None
    ) -> str:
        """
        Build RETURN clause for query.

        Args:
            node_alias: Alias for the product node
            include_score: Whether to include Lucene score
            relationship_alias: Alias for relationship (for priority)

        Returns:
            RETURN clause string
        """
        # Return individual fields that component_service._execute_search expects
        return_items = [
            f"{node_alias}.gin as gin",
            f"{node_alias}.item_name as name",
            f"{node_alias}.category as category",
            f"{node_alias}.clean_description as description",
            f"{node_alias} as specifications"
        ]

        if include_score:
            return_items.append("score")

        if relationship_alias and "COMPATIBLE_WITH" in str(relationship_alias):
            return_items.append(f"MIN({relationship_alias}.priority) as priority")

        return f"\nRETURN {', '.join(return_items)}"

    def extract_and_normalize_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text and normalize measurements.

        Reuses logic from product_search.py for consistency.

        Examples:
        - "Renegade ES300" → ["Renegade", "ES300"]
        - "5m interconnector" → ["5m", "5 m", "5.0 m", "5.0m", "interconnector"]
        - "70mm Gas-Cooled" → ["70mm", "70 mm", "70.0 mm", "70.0mm", "Gas-Cooled"]
        """
        keywords = []
        tokens = re.split(r'[\s,;]+', text)

        for token in tokens:
            if not token.strip():
                continue

            # Check if token contains measurement
            if re.search(r'\d+\.?\d*\s*(m|mm|cm|km)\b', token, flags=re.IGNORECASE):
                normalized = self._expand_measurement_terms(token)
                keywords.extend(normalized)
            else:
                keywords.append(token.strip())

        return keywords

    def _normalize_parameter_value(self, value: str, component_type: str) -> List[str]:
        """
        Normalize parameter values using comprehensive parameter_normalizations.json mappings.

        This replaces the old _expand_measurement_terms() method with a more robust
        approach that handles:
        - Cable lengths (2m, 5m, 10m, etc.)
        - Current ratings (300A, 400A, 500A, etc.)
        - Voltages (230V, 400V, 480V, etc.)
        - Wire diameters (0.8mm, 1.0mm, 1.2mm, etc.)
        - Cross sections (70mm², 95mm²)
        - Duty cycles (60%, 100%)
        - Cooling capacity (3L/min, 5L/min)
        - Swan neck angles (45°, 90°)

        Args:
            value: Parameter value to normalize (e.g., "5m", "500A", "70mm")
            component_type: Component type (e.g., "power_source", "feeder")

        Returns:
            List of normalized variants for fuzzy matching

        Examples:
            >>> _normalize_parameter_value("5m", "interconnector")
            ["5m", "5 m", "5.0m", "5 meter", "5 meters", "5-m"]

            >>> _normalize_parameter_value("500A", "power_source")
            ["500A", "500 A", "500amp", "500 ampere", "500 amps", "500-A"]

            >>> _normalize_parameter_value("70mm", "interconnector")
            ["70mm", "70mm²", "70mm2", "70 mm²", "70 mm2", "70mm squared", "70-mm²"]
        """
        if not value or not self.normalizations:
            return [value.strip()]

        value_normalized = value.strip().lower()

        # Check each normalization type relevant to this component
        applicable_params = self.component_parameter_mapping.get(component_type, [])

        for param_type in applicable_params:
            if param_type not in self.normalizations:
                continue

            mappings = self.normalizations[param_type].get("mappings", {})

            # Search for matching canonical value
            for canonical_value, variants in mappings.items():
                # Check if input matches any variant (case-insensitive)
                for variant in variants:
                    if variant.lower() == value_normalized:
                        logger.debug(
                            f"Normalized '{value}' → {len(variants)} variants for {param_type}"
                        )
                        return variants  # Return ALL variants for this canonical value

        # Fallback: Try basic pattern matching for unmapped values
        return self._fallback_normalization(value)

    def _fallback_normalization(self, value: str) -> List[str]:
        """
        Fallback normalization for values not in parameter_normalizations.json.

        Applies basic pattern matching for common measurement types.

        Args:
            value: Parameter value

        Returns:
            List of normalized variants
        """
        variants = [value.strip()]

        # Pattern 1: Length measurements (m, mm, cm, km)
        length_pattern = r'\b(\d+\.?\d*)\s*(m|mm|cm|km)\b'
        match = re.search(length_pattern, value, flags=re.IGNORECASE)
        if match:
            number = match.group(1)
            unit = match.group(2).lower()
            variants.append(f"{number} {unit}")
            if '.' not in number:
                variants.append(f"{number}.0 {unit}")
                variants.append(f"{number}.0{unit}")
            return variants

        # Pattern 2: Current ratings (A, amp, ampere)
        current_pattern = r'\b(\d+\.?\d*)\s*(?:A|amp|ampere)s?\b'
        match = re.search(current_pattern, value, flags=re.IGNORECASE)
        if match:
            number = match.group(1)
            variants.extend([f"{number}A", f"{number} A", f"{number}amp"])
            return variants

        # Pattern 3: Voltage (V, volt)
        voltage_pattern = r'\b(\d+\.?\d*)\s*(?:V|volt)s?\b'
        match = re.search(voltage_pattern, value, flags=re.IGNORECASE)
        if match:
            number = match.group(1)
            variants.extend([f"{number}V", f"{number} V", f"{number}volt"])
            return variants

        # Pattern 4: Percentages (%, percent)
        percent_pattern = r'\b(\d+\.?\d*)\s*(?:%|percent)\b'
        match = re.search(percent_pattern, value, flags=re.IGNORECASE)
        if match:
            number = match.group(1)
            variants.extend([f"{number}%", f"{number} %", f"{number}percent"])
            return variants

        return variants

    def build_search_terms_from_component(
        self,
        component_dict: Dict[str, Optional[str]],
        component_type: str
    ) -> Dict[str, Any]:
        """
        Build search terms from ALL extracted features (universal approach).

        USER REQUIREMENT (UNIVERSAL):
        "This approach works for all products - extract all features, normalize if needed,
         use CONTAINS against clean_description or attribute_ruleset.
         If product_name exists, also match on item_name."

        ENHANCED (Nov 15, 2024): Split comma-separated values for better matching
        - Process field: "MIG (GMAW), MAG, MMA/Stick" → ["MIG (GMAW)", "MAG", "MMA/Stick"]
        - Each individual term searched separately for ANY match (OR logic)

        Returns dict with:
        - "product_name": Original product_name for item_name CONTAINS matching (if exists)
        - "feature_terms": All extracted feature values (normalized) for description/attribute matching
        """
        result = {
            "product_name": None,
            "feature_terms": []
        }

        if not component_dict or not isinstance(component_dict, dict):
            return result

        for key, value in component_dict.items():
            if not value or not isinstance(value, str) or not value.strip():
                continue

            value_stripped = value.strip()

            if key == "product_name":
                # Check for GIN (skip if GIN detected)
                if re.match(r'^\d{10}$', value_stripped):
                    logger.info(f"GIN detected in product_name field: {value_stripped}")
                    continue

                result["product_name"] = value_stripped
                # Also add keywords from product_name to feature_terms
                keywords = self.extract_and_normalize_keywords(value_stripped)
                result["feature_terms"].extend(keywords)
            else:
                # 🔧 FIX (Nov 15, 2024): Split comma-separated values for better matching
                # Root cause: "MIG (GMAW), MAG, MMA/Stick, DC TIG (GTAW)" searched as single string
                # Solution: Split by comma and search each process individually
                if "," in value_stripped:
                    logger.info(f"Splitting comma-separated value for '{key}': {value_stripped}")
                    # Split by comma and process each term individually
                    individual_terms = [term.strip() for term in value_stripped.split(",")]
                    for term in individual_terms:
                        if term:  # Skip empty strings
                            normalized_terms = self._normalize_parameter_value(term, component_type)
                            result["feature_terms"].extend(normalized_terms)
                    logger.info(f"  → Split into {len(individual_terms)} individual terms")
                else:
                    # Single value - normalize as before
                    normalized_terms = self._normalize_parameter_value(value_stripped, component_type)
                    result["feature_terms"].extend(normalized_terms)

        logger.info(
            f"Extracted search terms: product_name='{result['product_name']}', "
            f"{len(result['feature_terms'])} feature terms: {result['feature_terms']}"
        )

        return result

    def _escape_lucene_special_chars(self, text: str) -> str:
        """
        Escape Lucene special characters in search text.

        Lucene query parser has special characters that need escaping:
        + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /

        Nov 15, 2024: Added to fix parsing errors when user queries contain
        special characters like "MIG/MAG" or "MMA (Stick)".

        Args:
            text: Raw search text

        Returns:
            Text with Lucene special characters escaped

        Example:
            >>> self._escape_lucene_special_chars("MIG/MAG welding")
            "MIG\\/MAG welding"
            >>> self._escape_lucene_special_chars("MMA (Stick) welding")
            "MMA \\(Stick\\) welding"
        """
        # Lucene special characters that need escaping with backslash
        special_chars = ['+', '-', '&', '|', '!', '(', ')', '{', '}', '[', ']',
                        '^', '"', '~', '*', '?', ':', '\\', '/']

        escaped_text = text
        for char in special_chars:
            # Escape each special character with backslash
            escaped_text = escaped_text.replace(char, f'\\{char}')

        return escaped_text

    def _remove_stopwords(self, text: str) -> str:
        """
        Remove stop words from search text.

        Stop words are common English words that don't contribute to search relevance
        (e.g., "I", "need", "want", "for", "a", "the", etc.).

        Nov 15, 2024: Imported from old product_search.py pattern for better Lucene matching.

        Args:
            text: Raw search text

        Returns:
            Text with stop words removed

        Example:
            >>> self._remove_stopwords("I need a 500A MIG welder")
            "500A MIG welder"
            >>> self._remove_stopwords("I want to find a machine for welding")
            "machine welding"
        """
        if not text or not isinstance(text, str):
            return text

        # Convert to lowercase and normalize whitespace
        clean = text.lower().strip()
        clean = re.sub(r'\s+', ' ', clean)

        # Split into words
        words = clean.split()

        # Remove stop words
        keywords = [
            w for w in words
            if w not in STOP_WORDS and len(w) > 1
        ]

        # If all words were stop words, keep words with length > 1
        if not keywords and words:
            keywords = [w for w in words if len(w) > 1]

        result = ' '.join(keywords)
        return result

    def _normalize_search_text(self, text: str) -> str:
        """
        Normalize measurement units in search text.

        Converts various unit formats to standardized forms that match database content.
        This preprocessing step improves Lucene search accuracy by ensuring consistent
        terminology between user queries and product descriptions.

        Nov 15, 2024: Imported from old product_search.py pattern.

        Args:
            text: Search text (typically after stop words removed)

        Returns:
            Normalized search text with standardized units

        Examples:
            >>> self._normalize_search_text("500 Amps MIG welder")
            "500 A MIG welder"
            >>> self._normalize_search_text("380 Volts 30mm wire")
            "380 V 30 mm wire"
            >>> self._normalize_search_text("18mm wire 3ph power")
            "18 mm wire 3 phase power"

        Normalization Rules:
            - Amperage: Amps/Ampere/Ampères → A
            - Voltage: Volts/Volt/Voltios → V
            - Length: meters/metres → m, millimeters/millimetres → mm
            - Power: Watts → W, kilowatts → kW
            - Pressure: Bar/BAR → bar
            - Flow: l/min, liters/minute → l/minute
            - Phase: 3ph, 1-phase → 3 phase, 1 phase
        """
        normalized = text

        # Rule 1: Add space between numbers and units if missing
        # "500A" → "500 A", "30mm" → "30 mm"
        normalized = re.sub(r'(\d+)([A-Za-z]+)', r'\1 \2', normalized)

        # Rule 2: Amperage - normalize to "A"
        # "500 Amps" → "500 A", "500 Ampere" → "500 A", "500 Ampères" → "500 A"
        normalized = re.sub(
            r'(\d+)\s*(Amps?|Amperes?|Ampères?)\b',
            r'\1 A',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 3: Voltage - normalize to "V"
        # "380 Volts" → "380 V", "460 Volt" → "460 V", "380 Voltios" → "380 V"
        normalized = re.sub(
            r'(\d+)\s*(Volts?|Voltios?)\b',
            r'\1 V',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 4: Power (Watts) - normalize to "W"
        # "500 Watts" → "500 W", "500 watt" → "500 W"
        normalized = re.sub(
            r'(\d+)\s*Watts?\b',
            r'\1 W',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 5: Power (Kilowatts) - normalize to "kW"
        # "4 kilowatt" → "4 kW", "4 kilowatts" → "4 kW"
        normalized = re.sub(
            r'(\d+)\s*kilowatts?\b',
            r'\1 kW',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 6: Length (meters) - normalize to "m"
        # "15 meters" → "15 m", "5 metre" → "5 m"
        normalized = re.sub(
            r'(\d+)\s*(meters?|metres?)\b',
            r'\1 m',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 7: Length (millimeters) - normalize to "mm"
        # "30 millimeters" → "30 mm", "1.2 millimetres" → "1.2 mm"
        normalized = re.sub(
            r'(\d+(?:\.\d+)?)\s*(millimeters?|millimetres?)\b',
            r'\1 mm',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 8: Length (inches) - normalize to "inch"
        # '32"' → "32 inch", "32 inches" → "32 inch"
        normalized = re.sub(
            r'(\d+)\s*(?:inches?|")\b',
            r'\1 inch',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 9: Pressure (bar) - normalize to lowercase "bar"
        # "5 Bar" → "5 bar", "5 BAR" → "5 bar"
        normalized = re.sub(
            r'(\d+)\s*bar\b',
            r'\1 bar',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 10: Flow rate - normalize to "l/minute"
        # "7 l/min" → "7 l/minute", "7 liters/minute" → "7 l/minute"
        normalized = re.sub(
            r'(\d+)\s*(?:l/min|liters?/min(?:ute)?|lpm)\b',
            r'\1 l/minute',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 11: Phase - normalize to "phase"
        # "3ph" → "3 phase", "1-phase" → "1 phase"
        normalized = re.sub(
            r'(\d+)[-\s]*ph\b',
            r'\1 phase',
            normalized,
            flags=re.IGNORECASE
        )

        # Rule 12: Duty cycle percent - preserve as-is
        # Already in correct format: "60%", "@60%", "at 60%"
        # No normalization needed for duty cycle

        return normalized.strip()
