package com.example.marketplace.service

import com.example.marketplace.dto.AuthRequest
import com.example.marketplace.dto.AuthResponse
import com.example.marketplace.dto.RegisterRequest
import com.example.marketplace.exception.InvalidCredentialsException
import com.example.marketplace.exception.UserAlreadyExistsException
import com.example.marketplace.model.User
import com.example.marketplace.repository.UserRepository
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.mockito.Mockito
import org.springframework.security.crypto.password.PasswordEncoder

class AuthServiceTest {

    private lateinit var authService: AuthService
    private lateinit var userRepository: UserRepository
    private lateinit var passwordEncoder: PasswordEncoder
    private lateinit var jwtConfig: JwtConfig
    private lateinit var userService: UserService

    @BeforeEach
    fun setUp() {
        userRepository = Mockito.mock(UserRepository::class.java)
        passwordEncoder = Mockito.mock(PasswordEncoder::class.java)
        jwtConfig = Mockito.mock(JwtConfig::class.java)
        userService = Mockito.mock(UserService::class.java)
        authService = AuthService(userRepository, passwordEncoder, jwtConfig, userService)
    }

    @Test
    fun `should authenticate user successfully`() {
        val authRequest = AuthRequest("test@example.com", "password123")
        val user = User(1L, "test@example.com", "Test User", "encodedPassword")
        val authResponse = AuthResponse("fake-token", com.example.marketplace.dto.UserDto(1L, "Test User", "test@example.com", "USER"))

        Mockito.`when`(userRepository.findByEmail("test@example.com")).thenReturn(user)
        Mockito.`when`(passwordEncoder.matches("password123", "encodedPassword")).thenReturn(true)
        Mockito.`when`(jwtConfig.generateToken("test@example.com")).thenReturn("fake-token")
        Mockito.`when`(userService.toDto(user)).thenReturn(authResponse.user)

        val result = authService.authenticate(authRequest)

        assert(result.token == "fake-token")
    }

    @Test
    fun `should throw exception when user not found`() {
        val authRequest = AuthRequest("nonexistent@example.com", "password123")

        Mockito.`when`(userRepository.findByEmail("nonexistent@example.com")).thenReturn(null)

        assertThrows<InvalidCredentialsException> {
            authService.authenticate(authRequest)
        }
    }

    @Test
    fun `should register new user successfully`() {
        val registerRequest = RegisterRequest("Test User", "test@example.com", "password123")
        val user = User(1L, "test@example.com", "Test User")
        val authResponse = AuthResponse("fake-token", com.example.marketplace.dto.UserDto(1L, "Test User", "test@example.com", "USER"))

        Mockito.`when`(userRepository.findByEmail("test@example.com")).thenReturn(null)
        Mockito.`when`(passwordEncoder.encode("password123")).thenReturn("encodedPassword")
        Mockito.`when`(userRepository.save(Mockito.any(User::class.java))).thenReturn(user)
        Mockito.`when`(jwtConfig.generateToken("test@example.com")).thenReturn("fake-token")
        Mockito.`when`(userService.toDto(user)).thenReturn(authResponse.user)

        val result = authService.register(registerRequest)

        assert(result.token == "fake-token")
    }

    @Test
    fun `should throw exception when user already exists`() {
        val registerRequest = RegisterRequest("Test User", "test@example.com", "password123")
        val existingUser = User(1L, "test@example.com", "Test User")

        Mockito.`when`(userRepository.findByEmail("test@example.com")).thenReturn(existingUser)

        assertThrows<UserAlreadyExistsException> {
            authService.register(registerRequest)
        }
    }
}