package com.example.marketplace.exception

import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice

@RestControllerAdvice
class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException::class)
    fun handleResourceNotFound(e: ResourceNotFoundException): ResponseEntity<ErrorResponse> {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(ErrorResponse(e.message ?: "Resource not found"))
    }

    @ExceptionHandler(InvalidCredentialsException::class)
    fun handleInvalidCredentials(e: InvalidCredentialsException): ResponseEntity<ErrorResponse> {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ErrorResponse(e.message ?: "Invalid credentials"))
    }

    @ExceptionHandler(UserAlreadyExistsException::class)
    fun handleUserAlreadyExists(e: UserAlreadyExistsException): ResponseEntity<ErrorResponse> {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(ErrorResponse(e.message ?: "User already exists"))
    }

    data class ErrorResponse(val message: String)
}