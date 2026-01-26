from datetime import datetime, date
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class ActivityLevel(Enum):
    VERY_LOW = 1.2
    LOW = 1.4
    MEDIUM = 1.6
    HIGH = 1.8
    VERY_HIGH = 2.0

    @property
    def display_name(self):
        names = {
            self.VERY_LOW: "Very low",
            self.LOW: "Low",
            self.MEDIUM: "Medium",
            self.HIGH: "High",
            self.VERY_HIGH: "Very high"}
        return names[self]


class DogHealthStatus(Enum):
    UNDERWEIGHT = "Underweight"
    IDEAL = "Ideal weight"
    OVERWEIGHT = "Overweight"
    OBESE = "Obese"


@dataclass
class WeightRecord:
    id: Optional[str] = None
    dog_name: str = ""
    date: datetime = None
    weight: float = 0.0
    notes: str = ""

    def __post_init__(self):
        if self.date is None:
            self.date = datetime.now()
        if self.id is None:
            self.id = f"{self.dog_name}_{self.date.timestamp()}"

    def to_dict(self):
        return {
            "id": self.id,
            "dog_name": self.dog_name,
            "date": self.date.isoformat(),
            "weight": self.weight,
            "notes": self.notes}

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id"),
            dog_name=data["dog_name"],
            date=datetime.fromisoformat(data["date"]),
            weight=data["weight"],
            notes=data.get("notes", ""))


class Dog:
    def __init__(self, name: str, breed: str, ideal_weight: float,
                 current_weight: float, birth_date: Optional[date] = None,
                 activity_level: ActivityLevel = ActivityLevel.MEDIUM):
        self.id = name.lower().replace(" ", "_")
        self.name = name
        self.breed = breed
        self.ideal_weight = ideal_weight
        self.current_weight = current_weight
        self.birth_date = birth_date
        self.activity_level = activity_level
        self.created_date = datetime.now()
        self.records: List[WeightRecord] = []

    @property
    def age(self) -> Optional[int]:
        if self.birth_date:
            today = date.today()
            age = today.year - self.birth_date.year
            if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
                age -= 1
            return age
        return None

    @property
    def health_status(self) -> DogHealthStatus:
        weight_ratio = self.current_weight / self.ideal_weight

        if weight_ratio < 0.85:
            return DogHealthStatus.UNDERWEIGHT
        elif weight_ratio <= 1.15:
            return DogHealthStatus.IDEAL
        elif weight_ratio <= 1.3:
            return DogHealthStatus.OVERWEIGHT
        else:
            return DogHealthStatus.OBESE

    @property
    def weight_to_lose(self) -> float:
        if self.current_weight > self.ideal_weight:
            return self.current_weight - self.ideal_weight
        return 0.0

    @property
    def bmi(self) -> float:
        return self.current_weight / self.ideal_weight

    def calculate_daily_calories(self, for_weight_loss: bool = True) -> float:
        resting_energy = 70 * (self.ideal_weight ** 0.75)
        daily_calories = resting_energy * self.activity_level.value

        if for_weight_loss:
            daily_calories *= 0.8

        return round(daily_calories, 1)

    def add_weight_record(self, weight: float, notes: str = "") -> WeightRecord:
        record = WeightRecord(
            dog_name=self.name,
            weight=weight,
            notes=notes)
        self.current_weight = weight
        self.records.append(record)
        return record

    def get_progress(self) -> List[WeightRecord]:
        return sorted(self.records, key=lambda x: x.date)

    def calculate_weekly_loss_rate(self) -> Optional[float]:
        if len(self.records) < 2:
            return None

        sorted_records = self.get_progress()
        first_record = sorted_records[0]
        last_record = sorted_records[-1]

        time_diff = (last_record.date - first_record.date).days / 7
        if time_diff == 0:
            return None

        weight_diff = last_record.weight - first_record.weight
        return weight_diff / time_diff

    def predict_goal_achievement(self) -> Optional[float]:
        weekly_rate = self.calculate_weekly_loss_rate()

        if weekly_rate and weekly_rate < 0:
            if self.current_weight > self.ideal_weight:
                weeks_needed = (self.current_weight - self.ideal_weight) / abs(weekly_rate)
                return max(weeks_needed, 0)
        return None

    def get_statistics(self) -> dict:
        progress = self.get_progress()

        stats = {
            "id": self.id,
            "name": self.name,
            "breed": self.breed,
            "age": self.age,
            "current_weight": self.current_weight,
            "ideal_weight": self.ideal_weight,
            "weight_to_lose": self.weight_to_lose,
            "bmi": round(self.bmi, 2),
            "health_status": self.health_status.value,
            "activity_level": self.activity_level.value,
            "activity_level_name": self.activity_level.display_name,
            "daily_calories_for_loss": self.calculate_daily_calories(for_weight_loss=True),
            "daily_calories_for_maintenance": self.calculate_daily_calories(for_weight_loss=False),
            "records_count": len(self.records),
            "weekly_loss_rate": self.calculate_weekly_loss_rate(),
            "weeks_to_goal": self.predict_goal_achievement()
        }

        if len(progress) >= 2:
            first_weight = progress[0].weight
            last_weight = progress[-1].weight
            stats["total_change"] = last_weight - first_weight
            stats["first_record_date"] = progress[0].date.isoformat()
            stats["last_record_date"] = progress[-1].date.isoformat()

        return stats

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "breed": self.breed,
            "ideal_weight": self.ideal_weight,
            "current_weight": self.current_weight,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "activity_level": self.activity_level.value,
            "created_date": self.created_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Dog':
        birth_date = None
        if data.get("birth_date"):
            birth_date = date.fromisoformat(data["birth_date"])

        dog = cls(
            name=data["name"],
            breed=data["breed"],
            ideal_weight=data["ideal_weight"],
            current_weight=data["current_weight"],
            birth_date=birth_date,
            activity_level=ActivityLevel(data["activity_level"]))

        if data.get("created_date"):
            dog.created_date = datetime.fromisoformat(data["created_date"])

        return dog
