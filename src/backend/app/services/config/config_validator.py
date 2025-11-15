"""
Configuration Validator Service
Validates configuration files against JSON schemas and performs cross-file consistency checks
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from jsonschema import validate, ValidationError, SchemaError
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    config_name: str

    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "config_name": self.config_name,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }


@dataclass
class ValidationReport:
    """Complete validation report for all configs"""
    results: List[ValidationResult]
    overall_valid: bool
    timestamp: str

    @classmethod
    def create(cls, results: List[ValidationResult]):
        """Create report from results"""
        from datetime import datetime
        return cls(
            results=results,
            overall_valid=all(r.is_valid for r in results),
            timestamp=datetime.utcnow().isoformat()
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "overall_valid": self.overall_valid,
            "timestamp": self.timestamp,
            "total_configs": len(self.results),
            "valid_configs": sum(1 for r in self.results if r.is_valid),
            "invalid_configs": sum(1 for r in self.results if not r.is_valid),
            "total_errors": sum(len(r.errors) for r in self.results),
            "total_warnings": sum(len(r.warnings) for r in self.results),
            "results": [r.to_dict() for r in self.results]
        }


class ConfigValidator:
    """
    Configuration validator with JSON schema validation and consistency checks
    """

    def __init__(self, config_dir: Optional[Path] = None, schema_dir: Optional[Path] = None):
        """
        Initialize validator

        Args:
            config_dir: Path to config directory (defaults to app/config)
            schema_dir: Path to schema directory (defaults to app/config/schemas)
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        if schema_dir is None:
            schema_dir = config_dir / "schemas"

        self.config_dir = Path(config_dir)
        self.schema_dir = Path(schema_dir)

        # Cache loaded schemas
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"ConfigValidator initialized - config_dir: {self.config_dir}, schema_dir: {self.schema_dir}")

    def load_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        Load JSON schema from schemas directory

        Args:
            schema_name: Name of schema file (without .json extension)

        Returns:
            Schema dictionary

        Raises:
            FileNotFoundError: If schema file doesn't exist
            json.JSONDecodeError: If schema is invalid JSON
        """
        if schema_name in self._schema_cache:
            return self._schema_cache[schema_name]

        schema_path = self.schema_dir / f"{schema_name}.schema.json"

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self._schema_cache[schema_name] = schema
        logger.debug(f"Loaded schema: {schema_name}")

        return schema

    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        Load configuration file

        Args:
            config_name: Name of config file (without .json extension)

        Returns:
            Config dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config is invalid JSON
        """
        config_path = self.config_dir / f"{config_name}.json"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        return config

    def validate_config_schema(self, config_name: str, schema_name: Optional[str] = None) -> ValidationResult:
        """
        Validate config file against its JSON schema

        Args:
            config_name: Name of config file to validate
            schema_name: Name of schema (defaults to config_name)

        Returns:
            ValidationResult with errors and warnings
        """
        if schema_name is None:
            schema_name = config_name

        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            config_name=config_name
        )

        try:
            # Load config and schema
            config = self.load_config(config_name)
            schema = self.load_schema(schema_name)

            # Validate against schema
            validate(instance=config, schema=schema)

            logger.info(f"✓ Config '{config_name}' passed schema validation")

        except FileNotFoundError as e:
            result.add_error(f"File not found: {str(e)}")
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {str(e)}")
        except ValidationError as e:
            result.add_error(f"Schema validation failed: {e.message}")
            if e.path:
                result.add_error(f"  Path: {'.'.join(str(p) for p in e.path)}")
        except SchemaError as e:
            result.add_error(f"Invalid schema: {str(e)}")
        except Exception as e:
            result.add_error(f"Unexpected error: {str(e)}")

        return result

    def validate_state_consistency(self) -> ValidationResult:
        """
        Validate consistency between component_types and state_prompts

        Checks:
        - All states in state_sequence have corresponding entries in state_prompts
        - All component state_names are in state_sequence
        - State order numbers are sequential and unique

        Returns:
            ValidationResult with consistency errors
        """
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            config_name="state_consistency"
        )

        try:
            component_types = self.load_config("component_types")
            state_prompts = self.load_config("state_prompts")

            # Get state sequence and finalize state
            state_sequence = component_types.get("state_sequence", [])
            finalize_state = component_types.get("finalize_state", "finalize")
            full_sequence = state_sequence + [finalize_state]

            # Check 1: All states in sequence have prompts
            prompt_states = set(state_prompts.get("states", {}).keys())
            for state in full_sequence:
                if state not in prompt_states:
                    result.add_error(f"State '{state}' in state_sequence missing from state_prompts.json")

            # Check 2: All component state_names are in sequence
            components = component_types.get("component_types", {})
            for comp_key, comp_data in components.items():
                state_name = comp_data.get("state_name")
                if state_name and state_name not in full_sequence:
                    result.add_error(
                        f"Component '{comp_key}' has state_name '{state_name}' "
                        f"not in state_sequence"
                    )

            # Check 3: State order numbers are sequential and unique
            state_orders = []
            for comp_key, comp_data in components.items():
                order = comp_data.get("state_order")
                if order:
                    state_orders.append((comp_key, order))

            state_orders.sort(key=lambda x: x[1])
            for i, (comp_key, order) in enumerate(state_orders, start=1):
                if order != i:
                    result.add_warning(
                        f"Component '{comp_key}' has state_order {order}, expected {i} "
                        f"for sequential ordering"
                    )

            # Check for duplicates
            order_counts = {}
            for comp_key, order in state_orders:
                order_counts[order] = order_counts.get(order, 0) + 1

            for order, count in order_counts.items():
                if count > 1:
                    result.add_error(f"Duplicate state_order {order} found in {count} components")

            # Check 4: State sequence length matches component count (excluding finalize)
            if len(state_sequence) != len(components):
                result.add_warning(
                    f"State sequence length ({len(state_sequence)}) != "
                    f"component count ({len(components)})"
                )

            if result.is_valid:
                logger.info("✓ State consistency validation passed")

        except Exception as e:
            result.add_error(f"Consistency check failed: {str(e)}")

        return result

    def validate_component_mappings(self) -> ValidationResult:
        """
        Validate component mappings across configs

        Checks:
        - All components in master_parameter_schema exist in component_types
        - All api_keys in powersource_state_specifications match component_types

        Returns:
            ValidationResult with mapping errors
        """
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            config_name="component_mappings"
        )

        try:
            component_types = self.load_config("component_types")
            master_schema = self.load_config("master_parameter_schema")
            applicability = self.load_config("powersource_state_specifications")

            # Get component keys from component_types
            component_keys = set(component_types.get("component_types", {}).keys())
            api_keys = set(
                data.get("api_key")
                for data in component_types.get("component_types", {}).values()
            )

            # Check 1: master_parameter_schema components exist in component_types
            schema_components = set(master_schema.get("components", {}).keys())
            for comp in schema_components:
                if comp not in component_keys:
                    result.add_error(
                        f"Component '{comp}' in master_parameter_schema.json "
                        f"not found in component_types.json"
                    )

            # Check 2: Applicability api_keys match component_types
            for ps_gin, ps_data in applicability.get("power_sources", {}).items():
                applicability_keys = set(ps_data.get("applicability", {}).keys())
                for key in applicability_keys:
                    if key not in api_keys:
                        result.add_warning(
                            f"Applicability key '{key}' for power source '{ps_gin}' "
                            f"not found in component_types api_keys"
                        )

            # Check default policy
            default_keys = set(applicability.get("default_policy", {}).get("applicability", {}).keys())
            for key in default_keys:
                if key not in api_keys:
                    result.add_warning(
                        f"Default policy key '{key}' not found in component_types api_keys"
                    )

            if result.is_valid:
                logger.info("✓ Component mapping validation passed")

        except Exception as e:
            result.add_error(f"Mapping validation failed: {str(e)}")

        return result

    def validate_all(self) -> ValidationReport:
        """
        Run all validations and generate comprehensive report

        Returns:
            ValidationReport with all results
        """
        logger.info("Starting comprehensive configuration validation...")

        results = []

        # Schema validations - Original 3 configs
        results.append(self.validate_config_schema("component_types"))
        results.append(self.validate_config_schema("state_prompts"))
        results.append(self.validate_config_schema("powersource_state_specifications"))

        # Schema validations - Additional configs (added Nov 2024)
        # Note: component_config merged into component_types (Nov 15, 2024)
        # Note: state_config merged into component_types (Nov 15, 2024)
        results.append(self.validate_config_schema("search_config"))
        results.append(self.validate_config_schema("master_parameter_schema"))

        # Consistency validations
        results.append(self.validate_state_consistency())
        results.append(self.validate_component_mappings())

        # Generate report
        report = ValidationReport.create(results)

        if report.overall_valid:
            logger.info("✅ All configuration validations passed")
        else:
            logger.error(f"❌ Configuration validation failed with {report.to_dict()['total_errors']} errors")

        return report

    def generate_validation_report(self) -> Dict[str, Any]:
        """
        Generate validation report as dictionary

        Returns:
            Report dictionary suitable for JSON serialization
        """
        report = self.validate_all()
        return report.to_dict()


# Singleton instance
_validator: Optional[ConfigValidator] = None


def get_validator() -> ConfigValidator:
    """Get singleton validator instance"""
    global _validator
    if _validator is None:
        _validator = ConfigValidator()
    return _validator


def validate_configs_on_startup() -> Tuple[bool, Dict[str, Any]]:
    """
    Validate all configs on application startup

    Returns:
        Tuple of (is_valid, report_dict)

    Raises:
        RuntimeError: If validation fails and raises exceptions
    """
    try:
        validator = get_validator()
        report = validator.validate_all()

        if not report.overall_valid:
            logger.error("Configuration validation failed on startup")
            logger.error(f"Report: {json.dumps(report.to_dict(), indent=2)}")

        return report.overall_valid, report.to_dict()

    except Exception as e:
        logger.exception(f"Fatal error during startup validation: {e}")
        raise RuntimeError(f"Configuration validation failed: {str(e)}")
