package com.example.marketplace.service

import com.example.marketplace.dto.TemplateCreateRequest
import com.example.marketplace.dto.TemplateUpdateRequest
import com.example.marketplace.exception.ResourceNotFoundException
import com.example.marketplace.model.Template
import com.example.marketplace.model.User
import com.example.marketplace.repository.TemplateRepository
import org.springframework.data.domain.Page
import org.springframework.data.domain.Pageable
import org.springframework.stereotype.Service

@Service
class TemplateService(
    private val templateRepository: TemplateRepository,
    private val userService: UserService
) {

    fun getAllTemplates(pageable: Pageable): Page<Template> {
        return templateRepository.findAll(pageable)
    }

    fun getTemplateById(id: Long): Template {
        return templateRepository.findById(id).orElseThrow {
            ResourceNotFoundException("Template not found with id: $id")
        }
    }

    fun createTemplate(templateCreateRequest: TemplateCreateRequest): Template {
        val author = userService.getCurrentUser()
        val template = Template(
            name = templateCreateRequest.name,
            description = templateCreateRequest.description,
            category = templateCreateRequest.category,
            price = templateCreateRequest.price.toBigDecimal(),
            screenshots = templateCreateRequest.screenshots,
            demoUrl = templateCreateRequest.demoUrl,
            builder = templateCreateRequest.builder,
            author = author
        )
        return templateRepository.save(template)
    }

    fun updateTemplate(id: Long, templateUpdateRequest: TemplateUpdateRequest): Template {
        val template = getTemplateById(id)
        val updatedTemplate = template.copy(
            name = templateUpdateRequest.name ?: template.name,
            description = templateUpdateRequest.description ?: template.description,
            category = templateUpdateRequest.category ?: template.category,
            price = templateUpdateRequest.price?.toBigDecimal() ?: template.price,
            screenshots = templateUpdateRequest.screenshots ?: template.screenshots,
            demoUrl = templateUpdateRequest.demoUrl ?: template.demoUrl,
            builder = templateUpdateRequest.builder ?: template.builder,
            updatedAt = java.time.LocalDateTime.now()
        )
        return templateRepository.save(updatedTemplate)
    }

    fun deleteTemplate(id: Long) {
        val template = getTemplateById(id)
        templateRepository.delete(template)
    }

    fun searchTemplates(category: String?, searchTerm: String?, pageable: Pageable): Page<Template> {
        return when {
            category != null && searchTerm != null -> {
                templateRepository.findByCategoryAndSearchTerm(category, searchTerm, pageable)
            }
            category != null -> {
                templateRepository.findByCategory(category, pageable)
            }
            searchTerm != null -> {
                templateRepository.findBySearchTerm(searchTerm, pageable)
            }
            else -> {
                templateRepository.findAll(pageable)
            }
        }
    }
}