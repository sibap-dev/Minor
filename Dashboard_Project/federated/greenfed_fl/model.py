"""Shared PyTorch MLP: 39 -> 128 -> 64 -> 34 with ReLU."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class ModelConfig:
    input_dim: int = 39
    hidden_dims: tuple[int, int] = (128, 64)
    num_classes: int = 34

    def build(self) -> "GreenFedMLP":
        return GreenFedMLP(
            input_dim=self.input_dim,
            hidden_dims=self.hidden_dims,
            num_classes=self.num_classes,
        )


class GreenFedMLP(nn.Module):
    def __init__(
        self,
        input_dim: int = 39,
        hidden_dims: tuple[int, int] = (128, 64),
        num_classes: int = 34,
    ) -> None:
        super().__init__()
        first, second = hidden_dims
        self.network = nn.Sequential(
            nn.Linear(input_dim, first),
            nn.ReLU(),
            nn.Linear(first, second),
            nn.ReLU(),
            nn.Linear(second, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


def model_parameter_count(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters()))


def model_state_bytes(model: nn.Module) -> int:
    """Bytes required to transmit one copy of the model parameters."""

    return int(
        sum(
            p.numel() * p.element_size()
            for p in model.parameters()
        )
    )
