from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Archivo de base de datos local SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./vocaloff.db"

# check_same_thread es obligatorio en SQLite cuando interactúa con peticiones asíncronas de FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Inyector de dependencia para obtener la sesión de BD en cada endpoint."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
