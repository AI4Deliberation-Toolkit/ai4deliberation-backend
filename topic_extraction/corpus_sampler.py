"""Year-stratified sampling for the opengov corpus refinement pass."""
import random
from dataclasses import dataclass


@dataclass
class SampledArticle:
    consultation_id: int
    article_id: int
    year: int
    title: str
    body_text: str

    @property
    def key(self) -> str:
        return f'{self.consultation_id}:{self.article_id}'


def sample_articles(
    parquet_path: str,
    sample_size: int,
    year_min: int,
    year_max: int,
    seed: int,
) -> list[SampledArticle]:
    """Pull a year-stratified random sample of articles from an opengov parquet.

    Distributes sample_size evenly across the years in [year_min, year_max].
    If a year has fewer articles than its quota, the shortfall is redistributed
    across years with remaining capacity. Returns fewer than sample_size only
    when the total candidate pool is smaller than sample_size.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path, columns=['consultation_id', 'start_date', 'articles'])
    rows = table.to_pylist()

    by_year: dict[int, list[SampledArticle]] = {}
    for row in rows:
        start_date = row.get('start_date')
        if start_date is None:
            continue
        year = start_date.year
        if year < year_min or year > year_max:
            continue
        cid = row['consultation_id']
        for art in row.get('articles') or []:
            title = (art.get('title') or '').strip()
            body = (art.get('body_text') or '').strip()
            if not title and not body:
                continue
            by_year.setdefault(year, []).append(SampledArticle(
                consultation_id=cid,
                article_id=art['article_id'],
                year=year,
                title=title,
                body_text=body,
            ))

    years = sorted(by_year.keys())
    if not years:
        return []

    rng = random.Random(seed)
    for year in years:
        rng.shuffle(by_year[year])

    base = sample_size // len(years)
    remainder = sample_size - base * len(years)

    sampled: list[SampledArticle] = []
    leftover: list[SampledArticle] = []
    for i, year in enumerate(years):
        candidates = by_year[year]
        target = base + (1 if i < remainder else 0)
        take = min(target, len(candidates))
        sampled.extend(candidates[:take])
        leftover.extend(candidates[take:])

    shortfall = sample_size - len(sampled)
    if shortfall > 0 and leftover:
        rng.shuffle(leftover)
        sampled.extend(leftover[:shortfall])

    return sampled
