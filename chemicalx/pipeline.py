"""A collection of full training and evaluation pipelines."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Mapping, Optional, Type, Union

import pandas as pd
import torch
from class_resolver import HintOrType
from sklearn.metrics import roc_auc_score
from torch.nn.modules.loss import _Loss
from torch.optim.optimizer import Optimizer
from tqdm import trange

from chemicalx.data import DatasetLoader, dataset_resolver
from chemicalx.models import Model, model_resolver
from chemicalx.version import __version__

__all__ = [
    "Result",
    "pipeline",
]


@dataclass
class Result:
    """A result package."""

    model: Model
    predictions: pd.DataFrame
    losses: List[float]
    train_time: float
    evaluation_time: float
    roc_auc: float

    def summarize(self) -> None:
        """Print results to the console."""
        print(f"AUC-ROC: {self.roc_auc:0.3f}")

    def save(self, directory: Union[str, Path]) -> None:
        """Save the results to a directory."""
        if isinstance(directory, str):
            directory = Path(directory)
        directory = directory.resolve()
        directory.mkdir(exist_ok=True, parents=True)

        torch.save(self.model, directory.joinpath("model.pkl"))
        directory.joinpath("results.json").write_text(
            json.dumps(
                {
                    "evaluation": {
                        "auc_roc": self.roc_auc,
                    },
                    "losses": self.losses,
                    "training_time": self.train_time,
                    "evaluation_time": self.evaluation_time,
                    "chemicalx_version": __version__,
                },
                indent=2,
            )
        )


def pipeline(
    *,
    dataset: HintOrType[DatasetLoader],
    model: HintOrType[Model],
    model_kwargs: Optional[Mapping[str, Any]] = None,
    optimizer_cls: Type[Optimizer] = torch.optim.Adam,
    optimizer_kwargs: Optional[Mapping[str, Any]] = None,
    loss_cls: Type[_Loss] = torch.nn.BCELoss,
    loss_kwargs: Optional[Mapping[str, Any]] = None,
    batch_size: int = 5120,
    epochs: int,
    context_features: bool,
    drug_features: bool,
    drug_molecules: bool,
    labels: bool,
) -> Result:
    """Run the training and evaluation pipeline.

    :param dataset:
        The dataset can be specified in one of three ways:

        1. The name of the dataset
        2. A subclass of :class:`chemicalx.DatasetLoader`
        3. An instance of a :class:`chemicalx.DatasetLoader`
    :param model:
        The model can be specified in one of three ways:

        1. The name of the model
        2. A subclass of :class:`chemicalx.Model`
        3. An instance of a :class:`chemicalx.Model`
    :param model_kwargs:
        Keyword arguments to pass through to the model constructor. Relevant if passing model by string or class.
    :param optimizer_cls:
        The class for the optimizer to use. Currently defaults to :class:`torch.optim.Adam`.
    :param optimizer_kwargs:
        Keyword arguments to pass through to the optimizer construction.
    :param loss_cls:
        The loss to use. If none given, uses :class:`torch.nn.BCELoss`.
    :param loss_kwargs:
        Keyword arguments to pass through to the loss construction.
    :param batch_size:
        The batch size
    :param epochs:
        The number of epochs to train
    :param context_features:
        Indicator whether the batch should include biological context features.
    :param drug_features:
        Indicator whether the batch should include drug features.
    :param drug_molecules:
        Indicator whether the batch should include drug molecules
    :param labels:
        Indicator whether the batch should include drug pair labels.
    :returns:
        A result object with the trained model and evaluation results
    """
    loader = dataset_resolver.make(dataset)
    train_generator, test_generator = loader.get_generators(
        batch_size=batch_size,
        context_features=context_features,
        drug_features=drug_features,
        drug_molecules=drug_molecules,
        labels=labels,
    )

    model = model_resolver.make(model, model_kwargs)

    optimizer = optimizer_cls(model.parameters(), **(optimizer_kwargs or {}))

    model.train()

    loss = loss_cls(**(loss_kwargs or {}))

    losses = []
    train_start_time = time.time()
    for _epoch in trange(epochs):
        for batch in train_generator:
            optimizer.zero_grad()
            prediction = model(*model.unpack(batch))
            loss_value = loss(prediction, batch.labels)
            losses.append(loss_value.item())
            loss_value.backward()
            optimizer.step()
    train_time = time.time() - train_start_time

    model.eval()

    evaluation_start_time = time.time()
    predictions = []
    for batch in test_generator:
        prediction = model(*model.unpack(batch))
        prediction = prediction.detach().cpu().numpy()
        identifiers = batch.identifiers
        identifiers["prediction"] = prediction
        predictions.append(identifiers)
    evaluation_time = time.time() - evaluation_start_time

    predictions_df = pd.concat(predictions)

    return Result(
        model=model,
        predictions=predictions_df,
        losses=losses,
        train_time=train_time,
        evaluation_time=evaluation_time,
        roc_auc=roc_auc_score(predictions_df["label"], predictions_df["prediction"]),
    )