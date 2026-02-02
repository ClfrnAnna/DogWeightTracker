from fastapi import FastAPI, HTTPException, Query, Body, Path, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import date, datetime
from enum import Enum
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession

from Dog import Dog, ActivityLevel, WeightRecord
from DogDBRepository import DogDBRepository
from database import get_db, create_tables

app = FastAPI(title="Dog Weight Tracker API (Database)",
              description="REST API микросервис для отслеживания веса собак с PostgreSQL",
              version="2.0.0",
              docs_url="/api/docs",
              redoc_url="/api/redoc",
              openapi_url="/api/openapi.json")

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"])

app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.on_event("startup")
async def startup():
    await create_tables()


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


@app.get("/", response_model=Dict[str, str])
async def root():
    return {"message": "Dog Weight Tracker API (Database Version)",
            "version": "2.0.0",
            "docs": "/api/docs",
            "database": "PostgreSQL"}


# Health check
@app.get("/api/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dogs_count = await repo.get_dogs_count()
    records_count = await repo.get_total_records_count()

    return HealthResponse(status="healthy",
                          timestamp=datetime.now(),
                          service="dog-weight-tracker-api-db",
                          version="2.0.0",
                          dogs_count=dogs_count,
                          records_count=records_count)


# Dogs endpoints
@app.get("/api/dogs", response_model=List[DogResponse])
async def get_all_dogs(skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
                       limit: int = Query(100, ge=1, le=100, description="Максимальное количество записей"),
                       db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dogs_db = await repo.get_all_dogs()

    dogs = []
    for dog_db in dogs_db:
        dog = repo.convert_to_dog_object(dog_db)
        records_db = await repo.get_dog_records(str(dog_db.id))
        dog.records = []
        for record_db in records_db:
            record = WeightRecord(id=str(record_db.id),
                                  dog_name=record_db.dog_name,
                                  date=record_db.date,
                                  weight=record_db.weight,
                                  notes=record_db.notes or "")
            dog.records.append(record)
        dogs.append(dog)

    result = []
    for dog in dogs[skip:skip + limit]:
        stats = dog.get_statistics()
        result.append(DogResponse(**stats))

    return result


@app.post("/api/dogs", response_model=DogResponse, status_code=status.HTTP_201_CREATED)
async def create_dog(dog_data: DogCreate,
                     db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)

    existing_dog = await repo.get_dog_by_name(dog_data.name)
    if existing_dog:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Собака с таким именем уже существует")

    activity_map = {ActivityLevelEnum.VERY_LOW: ActivityLevel.VERY_LOW,
                    ActivityLevelEnum.LOW: ActivityLevel.LOW,
                    ActivityLevelEnum.MEDIUM: ActivityLevel.MEDIUM,
                    ActivityLevelEnum.HIGH: ActivityLevel.HIGH,
                    ActivityLevelEnum.VERY_HIGH: ActivityLevel.VERY_HIGH}

    dog = Dog(name=dog_data.name,
              breed=dog_data.breed,
              ideal_weight=dog_data.ideal_weight,
              current_weight=dog_data.current_weight,
              birth_date=dog_data.birth_date,
              activity_level=activity_map[dog_data.activity_level])

    created_dog_db = await repo.add_dog(dog)
    await repo.add_weight_record(str(created_dog_db.id), dog_data.current_weight, "Начальные данные")

    created_dog_db = await repo.get_dog(str(created_dog_db.id))
    created_dog = repo.convert_to_dog_object(created_dog_db)

    return DogResponse(**created_dog.get_statistics())


@app.get("/api/dogs/{dog_id}", response_model=DogResponse)
async def get_dog(dog_id: str = Path(..., description="ID собаки"),
                  db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dog_db = await repo.get_dog(dog_id)

    if not dog_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")

    dog = repo.convert_to_dog_object(dog_db)

    records_db = await repo.get_dog_records(dog_id)
    dog.records = []
    for record_db in records_db:
        record = WeightRecord(id=str(record_db.id),
                              dog_name=record_db.dog_name,
                              date=record_db.date,
                              weight=record_db.weight,
                              notes=record_db.notes or "")
        dog.records.append(record)

    return DogResponse(**dog.get_statistics())


@app.put("/api/dogs/{dog_id}", response_model=DogResponse)
async def update_dog(dog_id: str = Path(..., description="ID собаки"),
                     dog_data: DogUpdate = Body(...),
                     db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    updates = {}

    if dog_data.activity_level:
        activity_map = {ActivityLevelEnum.VERY_LOW: ActivityLevel.VERY_LOW,
                        ActivityLevelEnum.LOW: ActivityLevel.LOW,
                        ActivityLevelEnum.MEDIUM: ActivityLevel.MEDIUM,
                        ActivityLevelEnum.HIGH: ActivityLevel.HIGH,
                        ActivityLevelEnum.VERY_HIGH: ActivityLevel.VERY_HIGH}
        updates["activity_level"] = activity_map[dog_data.activity_level].value

    for field, value in dog_data.dict(exclude_unset=True, exclude={"activity_level"}).items():
        if value is not None:
            updates[field] = value

    updated_dog_db = await repo.update_dog(dog_id, **updates)
    if not updated_dog_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")

    updated_dog_db = await repo.get_dog(dog_id)
    updated_dog = repo.convert_to_dog_object(updated_dog_db)

    records_db = await repo.get_dog_records(dog_id)
    updated_dog.records = []
    for record_db in records_db:
        record = WeightRecord(id=str(record_db.id),
                              dog_name=record_db.dog_name,
                              date=record_db.date,
                              weight=record_db.weight,
                              notes=record_db.notes or "")
        updated_dog.records.append(record)

    return DogResponse(**updated_dog.get_statistics())


@app.delete("/api/dogs/{dog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dog(dog_id: str = Path(..., description="ID собаки"),
                     db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    deleted = await repo.delete_dog(dog_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")


@app.get("/api/dogs/{dog_id}/records", response_model=List[dict])
async def get_dog_records(dog_id: str = Path(..., description="ID собаки"),
                          skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
                          limit: int = Query(100, ge=1, le=100, description="Максимальное количество записей"),
                          db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dog_db = await repo.get_dog(dog_id)

    if not dog_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")

    records_db = await repo.get_dog_records(dog_id)
    records = [record_db.to_dict() for record_db in records_db]

    return records[skip:skip + limit]


@app.post("/api/dogs/{dog_id}/weight", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_weight_record(dog_id: str = Path(..., description="ID собаки"),
                            record_data: WeightRecordCreate = Body(...),
                            db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dog_db = await repo.get_dog(dog_id)

    if not dog_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")

    record_db = await repo.add_weight_record(dog_id, record_data.weight, record_data.notes)
    if not record_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Не удалось добавить запись")

    return record_db.to_dict()


@app.get("/api/dogs/{dog_id}/statistics", response_model=dict)
async def get_dog_statistics(dog_id: str = Path(..., description="ID собаки"),
                             db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dog_db = await repo.get_dog(dog_id)

    if not dog_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")

    dog = repo.convert_to_dog_object(dog_db)

    records_db = await repo.get_dog_records(dog_id)
    dog.records = []
    for record_db in records_db:
        record = WeightRecord(id=str(record_db.id),
                              dog_name=record_db.dog_name,
                              date=record_db.date,
                              weight=record_db.weight,
                              notes=record_db.notes or "")
        dog.records.append(record)

    return dog.get_statistics()


@app.get("/api/calculate/calories", response_model=dict)
async def calculate_calories(dog_id: str = Query(..., description="ID собаки"),
                             for_weight_loss: bool = Query(True, description="Расчет для похудения"),
                             db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dog_db = await repo.get_dog(dog_id)

    if not dog_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Собака не найдена")

    dog = repo.convert_to_dog_object(dog_db)
    calories = dog.calculate_daily_calories(for_weight_loss)

    return {"dog_id": dog_id,
            "dog_name": dog.name,
            "for_weight_loss": for_weight_loss,
            "daily_calories": calories,
            "recommendation": f"Рекомендуемая дневная норма: {calories} ккал"}


@app.get("/api/records/recent", response_model=List[dict])
async def get_recent_records(limit: int = Query(10, ge=1, le=100, description="Количество последних записей"),
                             db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    records_db = await repo.get_recent_records(limit)
    return [record_db.to_dict() for record_db in records_db]


@app.get("/api/metrics", response_model=dict)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    repo = DogDBRepository(db)
    dogs_db = await repo.get_all_dogs()

    health_stats = {}
    for dog_db in dogs_db:
        dog = repo.convert_to_dog_object(dog_db)
        status = dog.health_status.value
        health_stats[status] = health_stats.get(status, 0) + 1

    dogs_count = await repo.get_dogs_count()
    records_count = await repo.get_total_records_count()

    return {"total_dogs": dogs_count,
            "total_records": records_count,
            "health_stats": health_stats,
            "avg_records_per_dog": records_count / dogs_count if dogs_count else 0,
            "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run("api_db:app",
                host="0.0.0.0",
                port=8000,
                log_level="info")
