import os
import json
from typing import List, Optional
from Dog import WeightRecord, Dog


class DogRepository:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.dogs_file = os.path.join(data_dir, "dogs.json")
        self.records_file = os.path.join(data_dir, "records.json")
        self._ensure_data_dir()
        self.dogs = self._load_dogs()
        self.records = self._load_records()
        self._link_records_to_dogs()

    def _ensure_data_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _load_dogs(self) -> dict:
        try:
            with open(self.dogs_file, 'r', encoding='utf-8') as f:
                dogs_data = json.load(f)
                return {dog["id"]: Dog.from_dict(dog) for dog in dogs_data}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _load_records(self) -> List[WeightRecord]:
        try:
            with open(self.records_file, 'r', encoding='utf-8') as f:
                records_data = json.load(f)
                return [WeightRecord.from_dict(record) for record in records_data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _link_records_to_dogs(self):
        for record in self.records:
            dog_id = record.dog_name.lower().replace(" ", "_")
            if dog_id in self.dogs:
                self.dogs[dog_id].records.append(record)

    def save(self):
        dogs_data = [dog.to_dict() for dog in self.dogs.values()]
        with open(self.dogs_file, 'w', encoding='utf-8') as f:
            json.dump(dogs_data, f, indent=2, ensure_ascii=False)

        records_data = [record.to_dict() for record in self.records]
        with open(self.records_file, 'w', encoding='utf-8') as f:
            json.dump(records_data, f, indent=2, ensure_ascii=False)

    def add_dog(self, dog: Dog) -> Dog:
        self.dogs[dog.id] = dog
        self.save()
        return dog

    def get_dog(self, dog_id: str) -> Optional[Dog]:
        return self.dogs.get(dog_id)

    def get_dog_by_name(self, name: str) -> Optional[Dog]:
        dog_id = name.lower().replace(" ", "_")
        return self.get_dog(dog_id)

    def get_all_dogs(self) -> List[Dog]:
        return list(self.dogs.values())

    def update_dog(self, dog_id: str, **kwargs) -> Optional[Dog]:
        dog = self.get_dog(dog_id)
        if dog:
            for key, value in kwargs.items():
                if hasattr(dog, key):
                    setattr(dog, key, value)
            self.save()
        return dog

    def delete_dog(self, dog_id: str) -> bool:
        if dog_id in self.dogs:
            self.records = [r for r in self.records if r.dog_name.lower().replace(" ", "_") != dog_id]
            del self.dogs[dog_id]
            self.save()
            return True
        return False

    def add_weight_record(self, dog_id: str, weight: float, notes: str = "") -> Optional[WeightRecord]:
        dog = self.get_dog(dog_id)
        if dog:
            record = dog.add_weight_record(weight, notes)
            self.records.append(record)
            self.save()
            return record
        return None

    def get_dog_records(self, dog_id: str) -> List[WeightRecord]:
        dog = self.get_dog(dog_id)
        if dog:
            return dog.get_progress()
        return []

    def get_recent_records(self, limit: int = 10) -> List[WeightRecord]:
        return sorted(self.records, key=lambda x: x.date, reverse=True)[:limit]
