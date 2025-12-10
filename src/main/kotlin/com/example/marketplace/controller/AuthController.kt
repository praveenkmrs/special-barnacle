package com.example.marketplace.controller

import com.example.marketplace.dto.AuthRequest
import com.example.marketplace.dto.AuthResponse
import com.example.marketplace.dto.RegisterRequest
import com.example.marketplace.service.AuthService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/auth")
class AuthController(
    private val authService: AuthService
) {

    @PostMapping("/login")
    fun login(@RequestBody authRequest: AuthRequest): ResponseEntity<AuthResponse> {
        return ResponseEntity.ok(authService.authenticate(authRequest))
    }

    @PostMapping("/register")
    fun register(@RequestBody registerRequest: RegisterRequest): ResponseEntity<AuthResponse> {
        return ResponseEntity.ok(authService.register(registerRequest))
    }

    @GetMapping("/oauth/{provider}")
    fun redirectToOAuth(@PathVariable provider: String): ResponseEntity<Unit> {
        // Implementation for redirecting to OAuth providers
        TODO("Implement OAuth redirect")
    }

    @GetMapping("/oauth/callback/{provider}")
    fun handleOAuthCallback(
        @PathVariable provider: String,
        @RequestParam code: String
    ): ResponseEntity<AuthResponse> {
        // Implementation for handling OAuth callback
        TODO("Implement OAuth callback handler")
    }
}