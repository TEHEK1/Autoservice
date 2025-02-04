from sqlalchemy import Column, Integer, String
from server.database import Base  # Импорт после того, как Base определен

class Service(Base):
    __tablename__ = 'services'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)

    def __repr__(self):
        return f"<Service(id={self.id}, name={self.name}, description={self.description})>"
