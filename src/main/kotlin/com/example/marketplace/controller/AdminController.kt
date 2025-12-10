package com.example.marketplace.controller

import com.example.marketplace.dto.SalesReport
import com.example.marketplace.dto.UserActivity
import com.example.marketplace.service.AdminService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/admin")
class AdminController(
    private val adminService: AdminService
) {

    @GetMapping("/sales-report")
    fun getSalesReport(): ResponseEntity<SalesReport> {
        return ResponseEntity.ok(adminService.getSalesReport())
    }

    @GetMapping("/user-activity")
    fun getUserActivity(): ResponseEntity<List<UserActivity>> {
        return ResponseEntity.ok(adminService.getUserActivity())
    }

    @GetMapping("/templates")
    fun getTemplates(): ResponseEntity<Unit> {
        // Implementation for getting all templates
        TODO("Implement templates listing")
    }
}