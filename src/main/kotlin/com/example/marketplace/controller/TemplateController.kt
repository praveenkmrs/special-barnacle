package com.example.marketplace.controller

import com.example.marketplace.dto.TemplateCreateRequest
import com.example.marketplace.dto.TemplateUpdateRequest
import com.example.marketplace.model.Template
import com.example.marketplace.service.TemplateService
import org.springframework.data.domain.Page
import org.springframework.data.domain.Pageable
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/templates")
class TemplateController(
    private val templateService: TemplateService
) {

    @GetMapping
    fun getAllTemplates(pageable: Pageable): ResponseEntity<Page<Template>> {
        return ResponseEntity.ok(templateService.getAllTemplates(pageable))
    }

    @GetMapping("/{id}")
    fun getTemplateById(@PathVariable id: Long): ResponseEntity<Template> {
        return ResponseEntity.ok(templateService.getTemplateById(id))
    }

    @PostMapping
    fun createTemplate(@RequestBody templateCreateRequest: TemplateCreateRequest): ResponseEntity<Template> {
        return ResponseEntity.ok(templateService.createTemplate(templateCreateRequest))
    }

    @PutMapping("/{id}")
    fun updateTemplate(
        @PathVariable id: Long,
        @RequestBody templateUpdateRequest: TemplateUpdateRequest
    ): ResponseEntity<Template> {
        return ResponseEntity.ok(templateService.updateTemplate(id, templateUpdateRequest))
    }

    @DeleteMapping("/{id}")
    fun deleteTemplate(@PathVariable id: Long): ResponseEntity<Unit> {
        templateService.deleteTemplate(id)
        return ResponseEntity.noContent().build()
    }

    @GetMapping("/search")
    fun searchTemplates(
        @RequestParam(required = false) category: String?,
        @RequestParam(required = false) searchTerm: String?,
        pageable: Pageable
    ): ResponseEntity<Page<Template>> {
        return ResponseEntity.ok(templateService.searchTemplates(category, searchTerm, pageable))
    }

    @PostMapping("/{id}/license")
    fun purchaseLicense(@PathVariable id: Long): ResponseEntity<Unit> {
        // Implementation for purchasing license
        TODO("Implement license purchase")
    }

    @PostMapping("/{id}/deploy")
    fun deployTemplate(@PathVariable id: Long): ResponseEntity<Unit> {
        // Implementation for deploying template
        TODO("Implement template deployment")
    }
}