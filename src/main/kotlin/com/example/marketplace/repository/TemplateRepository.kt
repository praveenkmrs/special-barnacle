package com.example.marketplace.repository

import com.example.marketplace.model.Template
import org.springframework.data.domain.Page
import org.springframework.data.domain.Pageable
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Query
import org.springframework.data.repository.query.Param
import org.springframework.stereotype.Repository

@Repository
interface TemplateRepository : JpaRepository<Template, Long> {
    
    fun findByCategory(category: String, pageable: Pageable): Page<Template>
    
    @Query("SELECT t FROM Template t WHERE LOWER(t.name) LIKE LOWER(CONCAT('%', :searchTerm, '%')) OR LOWER(t.description) LIKE LOWER(CONCAT('%', :searchTerm, '%'))")
    fun findBySearchTerm(@Param("searchTerm") searchTerm: String, pageable: Pageable): Page<Template>
    
    @Query("SELECT t FROM Template t WHERE t.category = :category AND (LOWER(t.name) LIKE LOWER(CONCAT('%', :searchTerm, '%')) OR LOWER(t.description) LIKE LOWER(CONCAT('%', :searchTerm, '%')))")
    fun findByCategoryAndSearchTerm(
        @Param("category") category: String,
        @Param("searchTerm") searchTerm: String,
        pageable: Pageable
    ): Page<Template>
}