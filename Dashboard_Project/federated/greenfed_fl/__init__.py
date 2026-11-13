"""GreenFed-IDS federated learning package.

Self-contained PyTorch implementation of Federated Averaging (FedAvg) with
pluggable client-selection strategies.  It intentionally does not depend on
Flower because the original Flower implementation is not present in this
repository and Flower is not installed in the verified environment.
"""

__version__ = "0.1.0"
