package com.example.marketplace.model

import java.math.BigDecimal
import java.time.LocalDateTime
import javax.persistence.*

@Entity
@Table(name = "templates")
data class Template(
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    val id: Long = 0,

    @Column(nullable = false)
    val name: String,

    @Column(length = 1000)
    val description: String,

    @Column(nullable = false)
    val category: String,

    @Column(nullable = false, precision = 10, scale = 2)
    val price: BigDecimal,

    @ElementCollection
    @CollectionTable(name = "template_screenshots", joinColumns = [JoinColumn(name = "template_id")])
    @Column(name = "screenshot_url")
    val screenshots: List<String>,

    @Column(nullable = false)
    val demoUrl: String,

    @Column(nullable = false)
    val builder: String,

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "author_id", nullable = false)
    val author: User,

    @Column(nullable = false)
    val createdAt: LocalDateTime = LocalDateTime.now(),

    @Column(nullable = false)
    val updatedAt: LocalDateTime = LocalDateTime.now()
)