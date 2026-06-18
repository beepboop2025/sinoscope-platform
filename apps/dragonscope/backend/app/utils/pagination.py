from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def paginate(
    session: AsyncSession,
    query: Select,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list, int]:
    """Execute a paginated query. Returns (items, total_count)."""
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch page
    paginated_query = query.limit(limit).offset(offset)
    result = await session.execute(paginated_query)
    items = list(result.scalars().all())

    return items, total
