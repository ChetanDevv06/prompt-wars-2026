"""
Equipment models: Equipment, EquipmentCompatibility, MaintenanceWindow.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import EquipmentCategory, EquipmentStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organisation import Laboratory
    from app.models.project import ProjectResourceRequirement
    from app.models.reservation import Reservation


class Equipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A piece of laboratory equipment that can be reserved.

    Each equipment record belongs to exactly one laboratory.
    """

    __tablename__ = "equipment"
    __table_args__ = (
        UniqueConstraint("serial_number", name="uq_equipment_serial_number"),
        CheckConstraint("length(trim(name)) > 0", name="ck_equipment_name_non_empty"),
        CheckConstraint("quantity >= 1", name="ck_equipment_quantity_positive"),
        Index("ix_equipment_laboratory_id", "laboratory_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Equipment display name")
    model: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Manufacturer model identifier"
    )
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Unique serial number (nullable for grouped items)"
    )
    category: Mapped[EquipmentCategory] = mapped_column(
        String(50),
        nullable=False,
        default=EquipmentCategory.OTHER,
        index=True,
        comment="Equipment category",
    )
    status: Mapped[EquipmentStatus] = mapped_column(
        String(30),
        nullable=False,
        default=EquipmentStatus.AVAILABLE,
        index=True,
        comment="Current operational status",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    specifications: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Technical specifications (free text or JSON)"
    )
    quantity: Mapped[int] = mapped_column(
        default=1, nullable=False, comment="Number of identical units available"
    )
    is_bookable: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="Whether this item can be reserved"
    )

    # FK
    laboratory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("laboratories.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    laboratory: Mapped[Laboratory] = relationship("Laboratory", back_populates="equipment")
    maintenance_windows: Mapped[list[MaintenanceWindow]] = relationship(
        "MaintenanceWindow", back_populates="equipment", cascade="all, delete-orphan"
    )
    compatible_as_primary: Mapped[list[EquipmentCompatibility]] = relationship(
        "EquipmentCompatibility",
        foreign_keys="EquipmentCompatibility.equipment_id",
        back_populates="equipment",
        cascade="all, delete-orphan",
    )
    compatible_as_alternative: Mapped[list[EquipmentCompatibility]] = relationship(
        "EquipmentCompatibility",
        foreign_keys="EquipmentCompatibility.compatible_equipment_id",
        back_populates="compatible_equipment",
    )
    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation", back_populates="equipment"
    )
    resource_requirements: Mapped[list[ProjectResourceRequirement]] = relationship(
        "ProjectResourceRequirement", back_populates="equipment"
    )

    def __repr__(self) -> str:
        return f"<Equipment id={self.id} name={self.name!r} status={self.status.value}>"


class EquipmentCompatibility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Declares that two pieces of equipment are compatible substitutes.

    The relationship is directional: equipment_id can be substituted by
    compatible_equipment_id. For bidirectional substitution, two records are needed.
    """

    __tablename__ = "equipment_compatibilities"
    __table_args__ = (
        UniqueConstraint(
            "equipment_id",
            "compatible_equipment_id",
            name="uq_equipment_compatibilities_pair",
        ),
        CheckConstraint(
            "equipment_id != compatible_equipment_id",
            name="ck_equipment_compatibilities_no_self_ref",
        ),
        Index("ix_equipment_compatibilities_equipment_id", "equipment_id"),
    )

    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    compatible_equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    equipment: Mapped[Equipment] = relationship(
        "Equipment",
        foreign_keys=[equipment_id],
        back_populates="compatible_as_primary",
    )
    compatible_equipment: Mapped[Equipment] = relationship(
        "Equipment",
        foreign_keys=[compatible_equipment_id],
        back_populates="compatible_as_alternative",
    )

    def __repr__(self) -> str:
        return f"<EquipmentCompatibility {self.equipment_id} → {self.compatible_equipment_id}>"


class MaintenanceWindow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Scheduled unavailability period for a piece of equipment.

    During a maintenance window the equipment cannot be reserved.
    """

    __tablename__ = "maintenance_windows"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_maintenance_windows_valid_range"),
        Index("ix_maintenance_windows_equipment_id", "equipment_id"),
        Index("ix_maintenance_windows_starts_at", "starts_at"),
    )

    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Maintenance window start (UTC)"
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Maintenance window end (UTC)"
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(
        default=False, nullable=False, comment="Whether this window is confirmed"
    )

    # Relationships
    equipment: Mapped[Equipment] = relationship("Equipment", back_populates="maintenance_windows")

    def __repr__(self) -> str:
        return (
            f"<MaintenanceWindow equipment={self.equipment_id} {self.starts_at} - {self.ends_at}>"
        )
