This repository provides a set of Python mixins and descriptors for creating dataclass-based serializers with robust import/export functionality. It enables seamless conversion between Python dataclasses and JSON-compatible dictionaries while handling complex data types and validation.

Key Features:
- ImportJsonMixin: Validates and imports dictionary data into dataclass instances with support for required field checking
- ExportJsonMixin: Recursively exports dataclass instances to JSON-serializable dictionaries
- FlatExportJsonMixin: Creates flat dictionary representations from nested dataclass structures
- Type Descriptors: Specialized descriptors for datetime, float, integer, and object handling with flexible parsing
- Object Support: Built-in support for single objects, object lists, and object maps with automatic instantiation
- Validation: Comprehensive field validation with customizable error handling

Use Cases:
- API request/response serialization
- Configuration file parsing and generation
- Data validation and transformation pipelines
- Object-relational mapping (ORM) utilities
- Structured data import/export systems

The library emphasizes type safety, flexible default values, and graceful error handling while maintaining clean, declarative dataclass definitions.
