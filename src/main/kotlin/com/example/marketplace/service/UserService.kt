package com.example.marketplace.service

import com.example.marketplace.dto.UserDto
import com.example.marketplace.exception.ResourceNotFoundException
import com.example.marketplace.model.User
import com.example.marketplace.repository.UserRepository
import org.springframework.security.core.context.SecurityContextHolder
import org.springframework.stereotype.Service

@Service
class UserService(
    private val userRepository: UserRepository
) {

    fun getCurrentUser(): User {
        val email = SecurityContextHolder.getContext().authentication.name
        return userRepository.findByEmail(email)
            ?: throw ResourceNotFoundException("Current user not found")
    }

    fun toDto(user: User): UserDto {
        return UserDto(
            id = user.id,
            name = user.name,
            email = user.email,
            role = user.role
        )
    }

    fun getUserById(id: Long): User {
        return userRepository.findById(id).orElseThrow {
            ResourceNotFoundException("User not found with id: $id")
        }
    }
}