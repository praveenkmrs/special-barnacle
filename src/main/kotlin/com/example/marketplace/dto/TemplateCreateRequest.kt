package com.example.marketplace.dto

data class TemplateCreateRequest(
    val name: String,
    val description: String,
    val category: String,
    val price: Double,
    val screenshots: List<String>,
    val demoUrl: String,
    val builder: String, // Bubble, Webflow etc.
    val authorId: Long
)