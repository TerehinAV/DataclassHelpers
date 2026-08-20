test:
    pytest

coverage:
    pytest --cov=descriptors --cov=mixins --cov-report=term-missing
