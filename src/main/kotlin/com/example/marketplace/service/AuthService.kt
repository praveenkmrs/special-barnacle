package com.example.marketplace.service

import com.example.marketplace.dto.AuthRequest
import com.example.marketplace.dto.AuthResponse
import com.example.marketplace.dto.RegisterRequest
import com.example.marketplace.exception.InvalidCredentialsException
import com.example.marketplace.exception.UserAlreadyExistsException
import com.example.marketplace.model.User
import com.example.marketplace.repository.UserRepository
import org.springframework.security.crypto.password.PasswordEncoder
import org.springframework.stereotype.Service

@Service
class AuthService(
    private val userRepository: UserRepository,
    private val passwordEncoder: PasswordEncoder,
    private val jwtConfig: JwtConfig,
    private val userService: UserService
) {

    fun authenticate(authRequest: AuthRequest): AuthResponse {
        val user = userRepository.findByEmail(authRequest.email)
            ?: throw InvalidCredentialsException("Invalid credentials")

        if (!passwordEncoder.matches(authRequest.password, user.password!!)) {
            throw InvalidCredentialsException("Invalid credentials")
        }

        val token = jwtConfig.generateToken(user.email)
        return AuthResponse(token, userService.toDto(user))
    }

    fun register(registerRequest: RegisterRequest): AuthResponse {
        if (userRepository.findByEmail(registerRequest.email) != null) {
            throw UserAlreadyExistsException("User already exists")
        }

        val encodedPassword = passwordEncoder.encode(registerRequest.password)
        val user = User(
            email = registerRequest.email,
            name = registerRequest.name,
            password = encodedPassword
        )

        val savedUser = userRepository.save(user)
        val token = jwtConfig.generateToken(savedUser.email)
        return AuthResponse(token, userService.toDto(savedUser))
    }
}