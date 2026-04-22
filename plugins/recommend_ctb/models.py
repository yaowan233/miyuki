import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Literal, Type

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession


class PlayerBP100Catch(SQLModel, table=True):
    __tablename__ = 'player_bp100_catch'
    player_id: int = Field(primary_key=True)
    beatmap_id: int = Field(primary_key=True)
    mod: int = Field(primary_key=True)
    bp_position: int = Field(primary_key=True)
    pp: float = Field()


class Covers(BaseModel):
    cover: str
    card: str
    list: str
    slimcover: str


class BeatmapsetCompact(BaseModel):
    artist: str
    artist_unicode: str
    covers: Covers
    creator: str
    favourite_count: int
    id: int
    nsfw: bool
    play_count: int
    preview_url: str
    source: str
    title: str
    title_unicode: str
    user_id: int
    status: str
    video: bool


class Beatmapset(BeatmapsetCompact):
    ...


class BeatmapCompact(BaseModel):
    beatmapset_id: int
    difficulty_rating: float
    id: int
    mode: Literal["fruits", "mania", "osu", "taiko"]
    status: str
    total_length: int
    user_id: int
    version: str
    checksum: Optional[str] = None
    beatmapset: Optional[Beatmapset] = None


class Beatmap(BeatmapCompact):
    accuracy: float
    ar: float
    bpm: Optional[float] = None
    convert: bool
    count_circles: int
    count_sliders: int
    count_spinners: int
    cs: float
    deleted_at: Optional[str] = None
    drain: float
    hit_length: int
    is_scoreable: bool
    last_updated: str
    mode_int: int
    passcount: int
    playcount: int
    ranked: int
    url: str


class Badge(BaseModel):
    awarded_at: str
    description: str
    image_url: str
    url: str


class GradeCounts(BaseModel):
    ssh: int
    ss: int
    sh: int
    s: int
    a: int


class Level(BaseModel):
    current: int
    progress: int


class Variant(BaseModel):
    mode: str
    variant: str
    country_rank: Optional[int] = None
    global_rank: Optional[int] = None
    pp: Optional[float] = None


class UserStatistics(BaseModel):
    grade_counts: GradeCounts
    hit_accuracy: float
    is_ranked: bool
    level: Level
    maximum_combo: int
    play_count: int
    play_time: int
    pp: int
    ranked_score: int
    replays_watched_by_others: int
    total_hits: int
    total_score: int
    global_rank: Optional[int] = None
    country_rank: Optional[int] = None
    badges: Optional[list[Badge]] = None
    variants: Optional[list[Variant]] = None


class UserCompact(BaseModel):
    avatar_url: str
    country_code: str
    default_group: str
    id: int
    is_active: bool
    is_bot: bool
    is_deleted: bool
    is_online: bool
    is_supporter: bool
    last_visit: Optional[str] = None
    profile_colour: Optional[str] = None
    username: str


class NewStatistics(BaseModel):
    great: Optional[int] = Field(default=0)
    large_tick_hit: Optional[int] = Field(default=0)
    small_tick_hit: Optional[int] = Field(default=0)
    small_tick_miss: Optional[int] = Field(default=0)
    miss: Optional[int] = Field(default=0)
    ok: Optional[int] = Field(default=0)
    meh: Optional[int] = Field(default=0)
    good: Optional[int] = Field(default=0)
    perfect: Optional[int] = Field(default=0)


class Settings(BaseModel):
    speed_change: Optional[float] = None
    circle_size: Optional[float] = None
    approach_rate: Optional[float] = None
    overall_difficulty: Optional[float] = None
    drain_rate: Optional[float] = None


class Mod(BaseModel):
    acronym: str


class Statistics(BaseModel):
    count_50: Optional[int] = None
    count_100: Optional[int] = None
    count_300: Optional[int] = None
    count_geki: Optional[int] = None
    count_katu: Optional[int] = None
    count_miss: Optional[int] = None


class NewScore(BaseModel):
    accuracy: float
    beatmap_id: int
    best_id: Optional[int] = None
    build_id: Optional[int] = None
    ended_at: str
    has_replay: bool
    id: int
    is_perfect_combo: bool
    legacy_perfect: bool
    legacy_score_id: Optional[int] = None
    legacy_total_score: int
    max_combo: Optional[int] = None
    mods: list[Mod]
    passed: bool
    pp: Optional[float] = None
    preserve: bool
    rank: str
    ranked: bool
    ruleset_id: int
    started_at: Optional[str] = None
    statistics: Optional[NewStatistics] = None
    total_score: int
    type: str
    user_id: int
    beatmap: Optional[Beatmap] = None
    beatmapset: Optional[Beatmapset] = None
    user: Optional[UserCompact] = None


class BeatmapRelationship(SQLModel):
    beatmap_id1: int = Field(primary_key=True)
    beatmap_id2: int = Field(primary_key=True)
    beatmap_mod1: int = Field(primary_key=True)
    beatmap_mod2: int = Field(primary_key=True)
    relationship_value: float = Field()


class User(SQLModel, table=True):
    __tablename__ = "User"
    id: int = Field(primary_key=True)
    """自增主键"""
    user_id: str = Field(index=True)
    """用户id"""
    osu_id: int = Field()
    """osu id"""
    osu_name: str = Field()
    """osu 用户名"""
    osu_mode: int = Field()
    """osu 模式"""
    lazer_mode: bool = Field()
    """是否启用lazer模式"""


beatmap_relationship_table = {}


def beatmap_relationship_factory(suffix: int) -> Type["BeatmapRelationship"]:
    class BeatmapRelationship(SQLModel, table=True):
        __tablename__ = f'beatmap_relationship_catch_{suffix}'
        beatmap_id1: int = Field(primary_key=True)
        beatmap_id2: int = Field(primary_key=True)
        beatmap_mod1: int = Field(primary_key=True)
        beatmap_mod2: int = Field(primary_key=True)
        relationship_value: float = Field()

    return BeatmapRelationship


for i in range(10):
    beatmap_relationship_table[i] = beatmap_relationship_factory(i)

beatmap_relationship_tables = beatmap_relationship_table.values()
engine = create_async_engine(
    "postgresql+asyncpg://postgres:mother2012@10.244.229.242:5432/beatmap_recommender",
)

osu_engine = create_async_engine(
    "postgresql+asyncpg://postgres:mother2012@10.244.229.242:5432/chat",
)



def get_beatmap_relationship_table(beatmap_id1: int, beatmap_id2: int) -> Type[BeatmapRelationship]:
    hash_value = (beatmap_id1 + beatmap_id2) % 10
    return beatmap_relationship_table[hash_value]


async def create_tables():
    async with engine.begin() as conn:
        # For SQLModel, this will create the tables (but won't drop existing ones)
        await conn.run_sync(SQLModel.metadata.create_all)
    # table_name = 'beatmap_relationship_catch_0'
    # table = SQLModel.metadata.tables.get(table_name)
    # print(table)


@asynccontextmanager
async def get_session() -> AsyncSession:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@asynccontextmanager
async def get_osu_session() -> AsyncSession:
    async_session = sessionmaker(osu_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


if __name__ == '__main__':
    asyncio.run(create_tables())
