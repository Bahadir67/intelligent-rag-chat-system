-- Conversation orders table
CREATE TABLE IF NOT EXISTS conversation_orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_id INTEGER REFERENCES products(id),
    quantity DECIMAL(10,3) NOT NULL,
    unit_price DECIMAL(15,4) NOT NULL,
    total_price DECIMAL(15,2) NOT NULL,
    order_status VARCHAR(20) DEFAULT 'pending',
    conversation_context JSONB,
    user_query TEXT,
    ai_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conv_orders_customer ON conversation_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_conv_orders_status ON conversation_orders(order_status);
CREATE INDEX IF NOT EXISTS idx_conv_orders_created ON conversation_orders(created_at);

-- Test customer
INSERT INTO customers (customer_code, company_name, country_code) 
VALUES ('CONV001', 'Konuşma Test Şirketi', 'TR') 
ON CONFLICT (customer_code) DO NOTHING;