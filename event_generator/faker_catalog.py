"""Seeded Faker-backed catalog data for generated web events."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from faker import Faker


@dataclass(frozen=True, slots=True)
class PageTarget:
    """Browser-visible page path and optional category represented by a page view."""

    path: str
    category_id: str | None = None


@dataclass(frozen=True, slots=True)
class Product:
    """Catalog product used to generate repeatable product interactions."""

    product_id: str
    category_id: str
    price_cents: int


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Repeatable fake user profile used as an analytics dimension."""

    user_id: str
    preferred_category_id: str


@dataclass(frozen=True, slots=True)
class CategoryTemplate:
    """Category generation template with realistic price bounds."""

    category_id: str
    slug: str
    min_price_cents: int
    max_price_cents: int


_FAKER_LOCALE = "en_US"
_USER_POOL_SIZE = 160
_PRODUCTS_PER_CATEGORY = 4
_CATEGORY_TEMPLATES: tuple[CategoryTemplate, ...] = (
    CategoryTemplate("cat_smartphone", "smartphone", 39_900, 129_900),
    CategoryTemplate("cat_laptop", "laptop", 79_900, 249_900),
    CategoryTemplate("cat_audio", "audio", 4_900, 49_900),
    CategoryTemplate("cat_accessory", "accessory", 900, 19_900),
)
_LANDING_PAGE_PATHS: tuple[str, ...] = (
    "/",
    "/products",
    "/products/new",
    "/products/best",
    "/cart",
    "/checkout",
    "/account/orders",
    "/support/returns",
)
_IDENTIFIER_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


class FakerDataCatalog:
    """Build deterministic browser page, user, and product pools from Faker."""

    def __init__(self, *, seed: int) -> None:
        """Create a seeded catalog whose values repeat for the same seed.

        Args:
            seed: Seed used by Faker's internal random source.
        """
        faker = Faker(_FAKER_LOCALE)
        faker.seed_instance(seed)

        self._faker = faker
        self.categories = _CATEGORY_TEMPLATES
        self.users = self._build_users()
        self.products = self._build_products()
        self.page_targets = self._build_page_targets()

    def products_for_category(self, category_id: str) -> tuple[Product, ...]:
        """Return products matching one category.

        Args:
            category_id: Category identifier to match.

        Returns:
            Tuple of products in the requested category.
        """
        return tuple(
            product for product in self.products if product.category_id == category_id
        )

    def page_targets_for_category(self, category_id: str) -> tuple[PageTarget, ...]:
        """Return category-specific page targets.

        Args:
            category_id: Category identifier to match.

        Returns:
            Tuple of page targets in the requested category.
        """
        return tuple(
            target for target in self.page_targets if target.category_id == category_id
        )

    def _build_users(self) -> tuple[UserProfile, ...]:
        user_ids: set[str] = set()
        users: list[UserProfile] = []
        category_ids = tuple(category.category_id for category in self.categories)

        while len(users) < _USER_POOL_SIZE:
            user_id = _unique_identifier(
                prefix="user",
                parts=(self._faker.uuid4().replace("-", ""),),
                existing=user_ids,
                max_slug_length=12,
            )
            preferred_category_id = cast(
                str,
                self._faker.random_element(elements=category_ids),
            )
            users.append(
                UserProfile(
                    user_id=user_id,
                    preferred_category_id=preferred_category_id,
                )
            )

        return tuple(users)

    def _build_products(self) -> tuple[Product, ...]:
        product_ids: set[str] = set()
        products: list[Product] = []

        for category in self.categories:
            for _ in range(_PRODUCTS_PER_CATEGORY):
                product_id = _unique_identifier(
                    prefix="prod",
                    parts=(
                        category.slug,
                        self._faker.color_name(),
                        self._faker.word(),
                    ),
                    existing=product_ids,
                    max_slug_length=44,
                )
                products.append(
                    Product(
                        product_id=product_id,
                        category_id=category.category_id,
                        price_cents=self._faker.random_int(
                            min=category.min_price_cents,
                            max=category.max_price_cents,
                            step=100,
                        ),
                    )
                )

        return tuple(products)

    def _build_page_targets(self) -> tuple[PageTarget, ...]:
        page_targets = [PageTarget(path) for path in _LANDING_PAGE_PATHS]
        seen_paths = {target.path for target in page_targets}

        for category in self.categories:
            page_targets.append(
                PageTarget(f"/categories/{category.slug}", category.category_id)
            )
            page_targets.append(
                PageTarget(f"/search/{self._faker.slug()}", category.category_id)
            )
            page_targets.append(
                PageTarget(
                    f"/collections/{_identifier_slug(self._faker.domain_word())}",
                    category.category_id,
                )
            )

        return tuple(_dedupe_page_targets(page_targets, seen_paths=seen_paths))


def _dedupe_page_targets(
    page_targets: Iterable[PageTarget],
    *,
    seen_paths: set[str],
) -> tuple[PageTarget, ...]:
    deduped: list[PageTarget] = []
    for target in page_targets:
        if target.path not in seen_paths:
            deduped.append(target)
            seen_paths.add(target.path)
        elif target.path in _LANDING_PAGE_PATHS:
            deduped.append(target)
    return tuple(deduped)


def _unique_identifier(
    *,
    prefix: str,
    parts: tuple[str, ...],
    existing: set[str],
    max_slug_length: int,
) -> str:
    slug = "_".join(
        filter(None, (_identifier_slug(part) for part in parts)),
    )[:max_slug_length].strip("_")
    candidate = f"{prefix}_{slug or 'item'}"
    suffix = 2
    while candidate in existing:
        candidate = f"{prefix}_{slug or 'item'}_{suffix}"
        suffix += 1
    existing.add(candidate)
    return candidate


def _identifier_slug(value: str) -> str:
    return _IDENTIFIER_SEPARATOR_PATTERN.sub("_", value.lower()).strip("_")
