from datetime import datetime

from pydantic import BaseModel


class BudgetDocument(BaseModel):
    user_id: str
    category_id: str
    limit_amount: float
    period: str  # "weekly" or "monthly"
    start_date: datetime
    end_date: datetime
