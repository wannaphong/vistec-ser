from vistec_ser.datasets import DataLoader, FeatureLoader
from vistec_ser.utils.config import Config
from vistec_ser.models import TestModel
import sys
import os


def main(argv):
    config_path, csv_path = argv[1], argv[2]
    assert os.path.exists(config_path), f"Config path `{config_path}` does not exists."
    assert os.path.exists(csv_path), f"CSV path `{csv_path}` does not exists."

    config = Config(path=config_path)
    feature_loader = FeatureLoader(config=config.feature_config)
    train_loader = DataLoader(feature_loader=feature_loader, csv_paths=csv_path, augmentations=config.augmentations)
    train_dataset = train_loader.get_dataset(batch_size=2)
    val_loader = DataLoader(feature_loader=feature_loader, csv_paths=csv_path)
    val_dataset = val_loader.get_dataset(batch_size=2)
    model = TestModel()
    model.compile(optimizer='sgd', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model.fit(train_dataset, validation_data=val_dataset, epochs=1)


if __name__ == '__main__':
    main(sys.argv)