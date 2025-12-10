package com.example.marketplace.dto

data class SalesReport(
    val totalRevenue: Double,
    val totalSales: Long,
    val monthlySales: Map<String, Long>
)