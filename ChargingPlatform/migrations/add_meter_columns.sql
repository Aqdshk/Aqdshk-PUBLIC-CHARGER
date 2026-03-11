-- Migration: Add meter_start, meter_stop, stop_reason to charging_sessions
-- Run on VPS: mysql -u charging_user -p charging_platform < ChargingPlatform/migrations/add_meter_columns.sql
-- Skip if columns already exist.

USE charging_platform;

ALTER TABLE charging_sessions ADD COLUMN meter_start INT NULL AFTER energy_consumed;
ALTER TABLE charging_sessions ADD COLUMN meter_stop INT NULL AFTER meter_start;
ALTER TABLE charging_sessions ADD COLUMN stop_reason VARCHAR(50) NULL AFTER meter_stop;
