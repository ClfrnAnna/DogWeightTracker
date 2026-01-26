from fastapi import FastAPI, HTTPException, Query, Body, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import date, datetime
from enum import Enum
import uvicorn

from Dog import Dog, ActivityLevel
from DogRepository import DogRepository

app = FastAPI(
    title="Dog Weight Tracker API",
    description="REST API микросервис для отслеживания веса собак",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], )

app.add_middleware(GZipMiddleware, minimum_size=1000)

repo = DogRepository()


class ActivityLevelEnum(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class DogCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Кличка собаки")
    breed: str = Field(..., min_length=1, max_length=50, description="Порода")
    ideal_weight: float = Field(..., gt=0, le=100, description="Идеальный вес в кг")
    current_weight: float = Field(..., gt=0, le=100, description="Текущий вес в кг")
    birth_date: Optional[date] = Field(None, description="Дата рождения (YYYY-MM-DD)")
    activity_level: ActivityLevelEnum = Field(ActivityLevelEnum.MEDIUM, description="Уровень активности")

    @validator('name')
    def name_alphanumeric(cls, v):
        if not v.replace(' ', '').isalnum():
            raise ValueError('Имя должно содержать только буквы, цифры и пробелы')
        return v


class DogUpdate(BaseModel):
    breed: Optional[str] = Field(None, min_length=1, max_length=50)
    ideal_weight: Optional[float] = Field(None, gt=0, le=100)
    current_weight: Optional[float] = Field(None, gt=0, le=100)
    birth_date: Optional[date] = Field(None)
    activity_level: Optional[ActivityLevelEnum] = Field(None)


class WeightRecordCreate(BaseModel):
    weight: float = Field(..., gt=0, le=100, description="Вес в кг")
    notes: Optional[str] = Field("", max_length=200, description="Примечания")


class DogResponse(BaseModel):
    id: str
    name: str
    breed: str
    age: Optional[int]
    current_weight: float
    ideal_weight: float
    weight_to_lose: float
    bmi: float
    health_status: str
    activity_level: float
    activity_level_name: str


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    service: str
    version: str
    dogs_count: int
    records_count: int


# Root endpoint
@app.get("/", response_model=Dict[str, str])
async def root():
    return {
        "message": "Dog Weight Tracker API",
        "version": "4.0.0",
        "docs": "/api/docs",
        "openapi": "/api/openapi.json"
    }


# Health check
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    dogs = repo.get_all_dogs()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        service="dog-weight-tracker-api",
        version="4.0.0",
        dogs_count=len(dogs),
        records_count=len(repo.records)
    )


# Dogs endpoints
@app.get("/api/dogs", response_model=List[DogResponse])
async def get_all_dogs(
        skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
        limit: int = Query(100, ge=1, le=100, description="Максимальное количество записей")):
    dogs = repo.get_all_dogs()
    return [DogResponse(**dog.get_statistics()) for dog in dogs[skip:skip + limit]]


@app.post("/api/dogs", response_model=DogResponse, status_code=status.HTTP_201_CREATED)
async def create_dog(dog_data: DogCreate):
    if repo.get_dog_by_name(dog_data.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Собака с таким именем уже существует")

    activity_map = {
        ActivityLevelEnum.VERY_LOW: ActivityLevel.VERY_LOW,
        ActivityLevelEnum.LOW: ActivityLevel.LOW,
        ActivityLevelEnum.MEDIUM: ActivityLevel.MEDIUM,
        ActivityLevelEnum.HIGH: ActivityLevel.HIGH,
        ActivityLevelEnum.VERY_HIGH: ActivityLevel.VERY_HIGH}
    dog = Dog(
        name=dog_data.name,
        breed=dog_data.breed,
        ideal_weight=dog_data.ideal_weight,
        current_weight=dog_data.current_weight,
        birth_date=dog_data.birth_date,
        activity_level=activity_map[dog_data.activity_level])

    created_dog = repo.add_dog(dog)
    repo.add_weight_record(created_dog.id, dog_data.current_weight, "Начальные данные")

    return DogResponse(**created_dog.get_statistics())


@app.get("/api/dogs/{dog_id}", response_model=DogResponse)
async def get_dog(dog_id: str = Path(..., description="ID собаки")):
    dog = repo.get_dog(dog_id)
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")
    return DogResponse(**dog.get_statistics())


@app.put("/api/dogs/{dog_id}", response_model=DogResponse)
async def update_dog(
        dog_id: str = Path(..., description="ID собаки"),
        dog_data: DogUpdate = Body(...)):
    updates = {}

    if dog_data.activity_level:
        activity_map = {
            ActivityLevelEnum.VERY_LOW: ActivityLevel.VERY_LOW,
            ActivityLevelEnum.LOW: ActivityLevel.LOW,
            ActivityLevelEnum.MEDIUM: ActivityLevel.MEDIUM,
            ActivityLevelEnum.HIGH: ActivityLevel.HIGH,
            ActivityLevelEnum.VERY_HIGH: ActivityLevel.VERY_HIGH
        }
        updates["activity_level"] = activity_map[dog_data.activity_level]

    for field, value in dog_data.dict(exclude_unset=True, exclude={"activity_level"}).items():
        if value is not None:
            updates[field] = value

    updated_dog = repo.update_dog(dog_id, **updates)
    if not updated_dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")

    return DogResponse(**updated_dog.get_statistics())


@app.delete("/api/dogs/{dog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dog(dog_id: str = Path(..., description="ID собаки")):
    if not repo.delete_dog(dog_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")


@app.get("/api/dogs/{dog_id}/records", response_model=List[dict])
async def get_dog_records(
        dog_id: str = Path(..., description="ID собаки"),
        skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
        limit: int = Query(100, ge=1, le=100, description="Максимальное количество записей")):

    dog = repo.get_dog(dog_id)
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")

    records = dog.get_progress()
    return [record.to_dict() for record in records[skip:skip + limit]]


@app.post("/api/dogs/{dog_id}/weight", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_weight_record(
        dog_id: str = Path(..., description="ID собаки"),
        record_data: WeightRecordCreate = Body(...)):
    dog = repo.get_dog(dog_id)
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")

    record = repo.add_weight_record(dog_id, record_data.weight, record_data.notes)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось добавить запись")

    return record.to_dict()


@app.get("/api/dogs/{dog_id}/statistics", response_model=dict)
async def get_dog_statistics(dog_id: str = Path(..., description="ID собаки")):
    dog = repo.get_dog(dog_id)
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")

    return dog.get_statistics()


@app.get("/api/calculate/calories", response_model=dict)
async def calculate_calories(
        dog_id: str = Query(..., description="ID собаки"),
        for_weight_loss: bool = Query(True, description="Расчет для похудения")):
    dog = repo.get_dog(dog_id)
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена"
        )

    calories = dog.calculate_daily_calories(for_weight_loss)
    return {
        "dog_id": dog_id,
        "dog_name": dog.name,
        "for_weight_loss": for_weight_loss,
        "daily_calories": calories,
        "recommendation": f"Рекомендуемая дневная норма: {calories} ккал"}


@app.get("/api/calculate/forecast", response_model=dict)
async def calculate_forecast(
        dog_id: str = Query(..., description="ID собаки"),
        weeks: int = Query(12, ge=1, le=52, description="Прогноз на количество недель")):
    dog = repo.get_dog(dog_id)
    if not dog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собака не найдена")

    progress = dog.get_progress()
    if len(progress) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно данных для прогноза")

    weekly_rate = dog.calculate_weekly_loss_rate()
    if not weekly_rate or weekly_rate >= 0:
        return {
            "dog_id": dog_id,
            "dog_name": dog.name,
            "message": "Недостаточно данных для прогноза или вес не уменьшается",
            "can_predict": False}

    weeks_to_goal = dog.predict_goal_achievement()
    forecast = []

    for week in range(0, weeks + 1, 4):
        projected_weight = dog.current_weight + (weekly_rate * week)
        if projected_weight < dog.ideal_weight:
            projected_weight = dog.ideal_weight

        forecast.append({
            "week": week,
            "projected_weight": round(projected_weight, 1),
            "status": "Цель достигнута" if projected_weight <= dog.ideal_weight else "В процессе"})

    return {
        "dog_id": dog_id,
        "dog_name": dog.name,
        "current_weight": dog.current_weight,
        "ideal_weight": dog.ideal_weight,
        "weekly_loss_rate": abs(weekly_rate),
        "weeks_to_goal": round(weeks_to_goal, 1) if weeks_to_goal else None,
        "forecast": forecast,
        "can_predict": True}


@app.get("/api/records/recent", response_model=List[dict])
async def get_recent_records(
        limit: int = Query(10, ge=1, le=100, description="Количество последних записей")):
    records = repo.get_recent_records(limit)
    return [record.to_dict() for record in records]


@app.get("/api/metrics", response_model=dict)
async def get_metrics():
    dogs = repo.get_all_dogs()
    health_stats = {}
    for dog in dogs:
        status = dog.health_status.value
        health_stats[status] = health_stats.get(status, 0) + 1

    return {
        "total_dogs": len(dogs),
        "total_records": len(repo.records),
        "health_stats": health_stats,
        "avg_records_per_dog": len(repo.records) / len(dogs) if dogs else 0,
        "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info")
