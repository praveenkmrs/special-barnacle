package com.example.marketplace.dto

data class TemplateUpdateRequest(
    val name: String? = null,
    val description: String? = null,
    val category: String? = null,
    val price: Double? = null,
    val screenshots: List<String>? = null,
    val demoUrl: String? = null,
    val builder: String? = null
)