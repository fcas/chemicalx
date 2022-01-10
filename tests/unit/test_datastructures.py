import unittest
import numpy as np
from chemicalx.data import ContextFeatureSet, DrugFeatureSet, LabelSet


class TestContextFeatureSet(unittest.TestCase):
    def setUp(self):
        self.context_feature_set = ContextFeatureSet()
        self.context_feature_set["context_1"] = np.array([0, 1, 2])
        self.context_feature_set["context_2"] = np.array([0, 1, 2])

    def test_ContextFeatureSet(self):
        assert self.context_feature_set["context_2"].shape == (3,)


class TestDrugFeatureSet(unittest.TestCase):
    def setUp(self):
        self.x = 2

    def test_DrugFeatureSet(self):
        data = DrugFeatureSet(x=self.x)
        assert data.x == 2


class TestLabelSet(unittest.TestCase):
    def setUp(self):
        self.x = 2

    def test_LabelSet(self):
        data = LabelSet(x=self.x)
        assert data.x == 2
