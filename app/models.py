from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(100), index=True)  # e.g., 'finnhub', 'newsapi'
    asset_type = Column(String(50), index=True)  # e.g., 'USD', 'GOLD', 'GENERAL'
    title = Column(String(500))
    content = Column(Text, nullable=True)
    url = Column(String(1000), unique=True)
    published_at = Column(DateTime(timezone=True))
    
    # Sentiment Analysis Results
    sentiment_label = Column(String(20), index=True)  # 'positive', 'negative', 'neutral'
    sentiment_score = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    watchlists = relationship("Watchlist", back_populates="owner", cascade="all, delete-orphan")
    portfolio_items = relationship("PortfolioItem", back_populates="owner", cascade="all, delete-orphan")

class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    asset_type = Column(String(50)) # e.g. "CRYPTO", "GENERAL"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="watchlists")

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    symbol = Column(String(50), index=True) # e.g. "BTC", "GOLD"
    amount = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    owner = relationship("User", back_populates="portfolio_items")
