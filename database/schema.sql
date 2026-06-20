-- ============================================================
-- Mini ERP — Database Schema (PostgreSQL-compatible DDL)
-- ============================================================
-- Run this file to create all tables from scratch.
-- Order respects foreign-key dependencies.
-- ============================================================

-- ----------------------------------------------------------
-- 1. USERS
-- ----------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(80)  NOT NULL UNIQUE,
    email           VARCHAR(120) NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    first_name      VARCHAR(80)  NOT NULL DEFAULT '',
    last_name       VARCHAR(80)  NOT NULL DEFAULT '',
    role            VARCHAR(30)  NOT NULL DEFAULT 'Sales User'
                        CHECK (role IN (
                            'Admin',
                            'Sales User',
                            'Purchase User',
                            'Manufacturing User',
                            'Inventory Manager',
                            'Business Owner'
                        )),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_users_email    ON users (email);
CREATE INDEX ix_users_username ON users (username);
CREATE INDEX ix_users_role     ON users (role);

-- ----------------------------------------------------------
-- 2. VENDORS
-- ----------------------------------------------------------
CREATE TABLE vendors (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200)   NOT NULL,
    email           VARCHAR(120)   NOT NULL DEFAULT '',
    phone           VARCHAR(30)    NOT NULL DEFAULT '',
    address_line1   VARCHAR(200)   NOT NULL DEFAULT '',
    address_line2   VARCHAR(200)   NOT NULL DEFAULT '',
    city            VARCHAR(100)   NOT NULL DEFAULT '',
    state           VARCHAR(100)   NOT NULL DEFAULT '',
    postal_code     VARCHAR(20)    NOT NULL DEFAULT '',
    country         VARCHAR(100)   NOT NULL DEFAULT '',
    tax_id          VARCHAR(50)    NOT NULL DEFAULT '',
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_vendors_name  ON vendors (name);
CREATE INDEX ix_vendors_email ON vendors (email);

-- ----------------------------------------------------------
-- 3. PRODUCTS
-- ----------------------------------------------------------
CREATE TABLE products (
    id                  SERIAL PRIMARY KEY,
    sku                 VARCHAR(50)    NOT NULL UNIQUE,
    name                VARCHAR(200)   NOT NULL,
    description         TEXT           NOT NULL DEFAULT '',
    category            VARCHAR(100)   NOT NULL DEFAULT '',
    unit_of_measure     VARCHAR(20)    NOT NULL DEFAULT 'units',
    unit_price          NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    cost_price          NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    on_hand_qty         NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    reserved_qty        NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    reorder_level       NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    procure_on_demand   BOOLEAN        NOT NULL DEFAULT FALSE,
    procurement_type    VARCHAR(15)    NOT NULL DEFAULT 'purchase'
                            CHECK (procurement_type IN ('purchase', 'manufacturing')),
    vendor_id           INTEGER        REFERENCES vendors(id) ON DELETE SET NULL,
    is_active           BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_products_sku      ON products (sku);
CREATE INDEX ix_products_category ON products (category);

-- ----------------------------------------------------------
-- 3. CUSTOMERS
-- ----------------------------------------------------------
CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200)   NOT NULL,
    email           VARCHAR(120)   NOT NULL DEFAULT '',
    phone           VARCHAR(30)    NOT NULL DEFAULT '',
    address_line1   VARCHAR(200)   NOT NULL DEFAULT '',
    address_line2   VARCHAR(200)   NOT NULL DEFAULT '',
    city            VARCHAR(100)   NOT NULL DEFAULT '',
    state           VARCHAR(100)   NOT NULL DEFAULT '',
    postal_code     VARCHAR(20)    NOT NULL DEFAULT '',
    country         VARCHAR(100)   NOT NULL DEFAULT '',
    tax_id          VARCHAR(50)    NOT NULL DEFAULT '',
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_customers_name  ON customers (name);
CREATE INDEX ix_customers_email ON customers (email);



-- ----------------------------------------------------------
-- 5. SALES ORDERS
-- ----------------------------------------------------------
CREATE TABLE sales_orders (
    id              SERIAL PRIMARY KEY,
    order_number    VARCHAR(30)    NOT NULL UNIQUE,
    customer_id     INTEGER        NOT NULL REFERENCES customers(id),
    user_id         INTEGER        NOT NULL REFERENCES users(id),
    status          VARCHAR(20)    NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'confirmed', 'processing',
                            'shipped', 'delivered', 'cancelled'
                        )),
    order_date      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expected_date   TIMESTAMP,
    subtotal        NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    tax_amount      NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    total_amount    NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    notes           TEXT           NOT NULL DEFAULT '',
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_sales_orders_order_number ON sales_orders (order_number);
CREATE INDEX ix_sales_orders_customer_id  ON sales_orders (customer_id);
CREATE INDEX ix_sales_orders_user_id      ON sales_orders (user_id);
CREATE INDEX ix_sales_orders_status       ON sales_orders (status);

-- ----------------------------------------------------------
-- 6. SALES ORDER LINES
-- ----------------------------------------------------------
CREATE TABLE sales_order_lines (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER        NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id      INTEGER        NOT NULL REFERENCES products(id),
    quantity        NUMERIC(12,2)  NOT NULL DEFAULT 1.00,
    unit_price      NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    discount_pct    NUMERIC(5,2)   NOT NULL DEFAULT 0.00,
    line_total      NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_sol_order_id   ON sales_order_lines (order_id);
CREATE INDEX ix_sol_product_id ON sales_order_lines (product_id);

-- ----------------------------------------------------------
-- 7. PURCHASE ORDERS
-- ----------------------------------------------------------
CREATE TABLE purchase_orders (
    id              SERIAL PRIMARY KEY,
    order_number    VARCHAR(30)    NOT NULL UNIQUE,
    vendor_id       INTEGER        NOT NULL REFERENCES vendors(id),
    user_id         INTEGER        NOT NULL REFERENCES users(id),
    status          VARCHAR(20)    NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'confirmed', 'shipped',
                            'received', 'cancelled'
                        )),
    order_date      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expected_date   TIMESTAMP,
    subtotal        NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    tax_amount      NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    total_amount    NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    notes           TEXT           NOT NULL DEFAULT '',
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_purchase_orders_order_number ON purchase_orders (order_number);
CREATE INDEX ix_purchase_orders_vendor_id    ON purchase_orders (vendor_id);
CREATE INDEX ix_purchase_orders_user_id      ON purchase_orders (user_id);
CREATE INDEX ix_purchase_orders_status       ON purchase_orders (status);

-- ----------------------------------------------------------
-- 8. PURCHASE ORDER LINES
-- ----------------------------------------------------------
CREATE TABLE purchase_order_lines (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER        NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id      INTEGER        NOT NULL REFERENCES products(id),
    quantity        NUMERIC(12,2)  NOT NULL DEFAULT 1.00,
    unit_price      NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    line_total      NUMERIC(14,2)  NOT NULL DEFAULT 0.00,
    received_qty    NUMERIC(12,2)  NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_pol_order_id   ON purchase_order_lines (order_id);
CREATE INDEX ix_pol_product_id ON purchase_order_lines (product_id);

-- ----------------------------------------------------------
-- 9. BILL OF MATERIALS (header)
-- ----------------------------------------------------------
CREATE TABLE bill_of_materials (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER        NOT NULL REFERENCES products(id),
    name            VARCHAR(200)   NOT NULL,
    version         VARCHAR(20)    NOT NULL DEFAULT '1.0',
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    output_qty      NUMERIC(12,2)  NOT NULL DEFAULT 1.00,
    notes           TEXT           NOT NULL DEFAULT '',
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_bom_product_id ON bill_of_materials (product_id);

-- ----------------------------------------------------------
-- 10. BOM LINES (components)
-- ----------------------------------------------------------
CREATE TABLE bom_lines (
    id              SERIAL PRIMARY KEY,
    bom_id          INTEGER        NOT NULL REFERENCES bill_of_materials(id) ON DELETE CASCADE,
    component_id    INTEGER        NOT NULL REFERENCES products(id),
    quantity        NUMERIC(12,4)  NOT NULL DEFAULT 1.0000,
    unit_of_measure VARCHAR(20)    NOT NULL DEFAULT 'units',
    notes           TEXT           NOT NULL DEFAULT ''
);

CREATE INDEX ix_bom_lines_bom_id        ON bom_lines (bom_id);
CREATE INDEX ix_bom_lines_component_id  ON bom_lines (component_id);

-- ----------------------------------------------------------
-- 11. BOM OPERATIONS (routing steps)
-- ----------------------------------------------------------
CREATE TABLE bom_operations (
    id              SERIAL PRIMARY KEY,
    bom_id          INTEGER        NOT NULL REFERENCES bill_of_materials(id) ON DELETE CASCADE,
    sequence        INTEGER        NOT NULL DEFAULT 10,
    name            VARCHAR(200)   NOT NULL,
    work_center     VARCHAR(100)   NOT NULL DEFAULT '',
    duration_minutes NUMERIC(8,2)  NOT NULL DEFAULT 0.00,
    notes           TEXT           NOT NULL DEFAULT ''
);

CREATE INDEX ix_bom_ops_bom_id ON bom_operations (bom_id);

-- ----------------------------------------------------------
-- 12. MANUFACTURING ORDERS
-- ----------------------------------------------------------
CREATE TABLE manufacturing_orders (
    id              SERIAL PRIMARY KEY,
    order_number    VARCHAR(30)    NOT NULL UNIQUE,
    product_id      INTEGER        NOT NULL REFERENCES products(id),
    bom_id          INTEGER        NOT NULL REFERENCES bill_of_materials(id),
    user_id         INTEGER        NOT NULL REFERENCES users(id),
    quantity        NUMERIC(12,2)  NOT NULL DEFAULT 1.00,
    status          VARCHAR(20)    NOT NULL DEFAULT 'draft'
                        CHECK (status IN (
                            'draft', 'confirmed', 'in_progress',
                            'done', 'cancelled'
                        )),
    planned_start   TIMESTAMP,
    planned_end     TIMESTAMP,
    actual_start    TIMESTAMP,
    actual_end      TIMESTAMP,
    notes           TEXT           NOT NULL DEFAULT '',
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_mo_order_number ON manufacturing_orders (order_number);
CREATE INDEX ix_mo_product_id   ON manufacturing_orders (product_id);
CREATE INDEX ix_mo_bom_id       ON manufacturing_orders (bom_id);
CREATE INDEX ix_mo_status       ON manufacturing_orders (status);

-- ----------------------------------------------------------
-- 13. WORK ORDERS (per-operation execution)
-- ----------------------------------------------------------
CREATE TABLE work_orders (
    id                      SERIAL PRIMARY KEY,
    manufacturing_order_id  INTEGER        NOT NULL REFERENCES manufacturing_orders(id) ON DELETE CASCADE,
    bom_operation_id        INTEGER        NOT NULL REFERENCES bom_operations(id),
    sequence                INTEGER        NOT NULL DEFAULT 10,
    status                  VARCHAR(20)    NOT NULL DEFAULT 'pending'
                                CHECK (status IN (
                                    'pending', 'in_progress', 'done', 'cancelled'
                                )),
    planned_duration_min    NUMERIC(8,2)   NOT NULL DEFAULT 0.00,
    actual_duration_min     NUMERIC(8,2)   NOT NULL DEFAULT 0.00,
    started_at              TIMESTAMP,
    finished_at             TIMESTAMP,
    notes                   TEXT           NOT NULL DEFAULT '',
    created_at              TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_wo_mo_id        ON work_orders (manufacturing_order_id);
CREATE INDEX ix_wo_bom_op_id    ON work_orders (bom_operation_id);
CREATE INDEX ix_wo_status       ON work_orders (status);

-- ----------------------------------------------------------
-- 14. STOCK LEDGER
-- ----------------------------------------------------------
CREATE TABLE stock_ledger (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER        NOT NULL REFERENCES products(id),
    movement_type   VARCHAR(30)    NOT NULL
                        CHECK (movement_type IN (
                            'purchase_receipt', 'sales_issue',
                            'manufacturing_consume', 'manufacturing_produce',
                            'adjustment', 'reservation', 'reservation_release',
                            'transfer', 'return'
                        )),
    quantity         NUMERIC(12,2)  NOT NULL,
    reference_type   VARCHAR(30)    NOT NULL DEFAULT '',
    reference_id     INTEGER,
    description      TEXT           NOT NULL DEFAULT '',
    user_id          INTEGER        REFERENCES users(id),
    created_at       TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_stock_ledger_product_id     ON stock_ledger (product_id);
CREATE INDEX ix_stock_ledger_movement_type  ON stock_ledger (movement_type);
CREATE INDEX ix_stock_ledger_reference      ON stock_ledger (reference_type, reference_id);
CREATE INDEX ix_stock_ledger_created_at     ON stock_ledger (created_at);

-- ----------------------------------------------------------
-- 15. AUDIT LOGS
-- ----------------------------------------------------------
CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    table_name      VARCHAR(80)    NOT NULL,
    record_id       INTEGER        NOT NULL,
    action          VARCHAR(10)    NOT NULL
                        CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_values      JSONB,
    new_values      JSONB,
    user_id         INTEGER        REFERENCES users(id),
    ip_address      VARCHAR(45)    NOT NULL DEFAULT '',
    user_agent      VARCHAR(300)   NOT NULL DEFAULT '',
    created_at      TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_audit_logs_table_name ON audit_logs (table_name);
CREATE INDEX ix_audit_logs_record_id  ON audit_logs (record_id);
CREATE INDEX ix_audit_logs_user_id    ON audit_logs (user_id);
CREATE INDEX ix_audit_logs_action     ON audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);
