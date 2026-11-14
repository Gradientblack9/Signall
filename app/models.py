from typing import Literal

from pydantic import BaseModel, Field

Category = Literal['Customers', 'Competitors', 'Market', 'Internal']


class Fact(BaseModel):
    claim: str
    status: Literal['verified', 'assumption']
    url: str = ''
    quote: str = ''


class Competitor(BaseModel):
    name: str
    url: str
    reason: str


class Profile(BaseModel):
    summary: str
    industry: str
    customers: list[str]
    products: list[str]
    priorities: list[str]
    facts: list[Fact]
    competitors: list[Competitor]


class Question(BaseModel):
    question: str
    why: str


class FollowUp(BaseModel):
    question: str


class SearchPlan(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=10)


class Candidate(BaseModel):
    url: str
    name: str
    category: Category
    reason: str
    specificity: float = Field(ge=0, le=1)
    recency: float = Field(ge=0, le=1)
    credibility: float = Field(ge=0, le=1)
    relevance: float = Field(ge=0, le=1)


class Candidates(BaseModel):
    sources: list[Candidate]
    competitors: list[Competitor]


class SourceHypotheses(Candidates):
    sources: list[Candidate] = Field(min_length=24, max_length=36)
    competitors: list[Competitor] = Field(min_length=5, max_length=10)


class Interpretation(BaseModel):
    what: str
    why_it_matters: str
    business_area: str
    sentiment: Literal['opportunity', 'threat', 'neutral']
    urgency: Literal['low', 'medium', 'high']
    suggested_action: str
    relevance: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    urgency_score: float = Field(ge=0, le=1)
    evidence_strength: float = Field(ge=0, le=1)
    evidence_quote: str
    internal_type: Literal['objection', 'lost_deal', 'product_request', 'sales_pattern', 'risk', 'other'] = 'other'
    suggested_owner: str = 'Strategy lead (suggested role)'
    competitor_name: str = ''
    is_development: bool = True
    event_date: str = ''
    watch_reason: str = ''


class Reassessment(BaseModel):
    class SourceScore(BaseModel):
        id: int
        relevance: float = Field(ge=0, le=1)
        reason: str

    sources: list[SourceScore]
    new_queries: list[str]


class OpportunityIdea(BaseModel):
    signal_ids: list[int] = Field(min_length=1, max_length=5)
    title: str
    impact_statement: str
    next_step: str
    priority: Literal['high', 'medium', 'low']
    suggested_owner: str


class OpportunityPlan(BaseModel):
    opportunities: list[OpportunityIdea] = Field(max_length=6)
