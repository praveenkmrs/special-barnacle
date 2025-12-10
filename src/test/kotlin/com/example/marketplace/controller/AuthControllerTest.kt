package com.example.marketplace.controller

import com.example.marketplace.dto.AuthRequest
import com.example.marketplace.dto.AuthResponse
import com.example.marketplace.dto.RegisterRequest
import com.example.marketplace.service.AuthService
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.mockito.Mockito
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest
import org.springframework.boot.test.mock.mockito.MockBean
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status

@WebMvcTest(AuthController::class)
class AuthControllerTest {

    @Autowired
    private lateinit var mockMvc: MockMvc

    @MockBean
    private lateinit var authService: AuthService

    private lateinit var authRequest: AuthRequest
    private lateinit var registerRequest: RegisterRequest
    private lateinit var authResponse: AuthResponse

    @BeforeEach
    fun setUp() {
        authRequest = AuthRequest("test@example.com", "password123")
        registerRequest = RegisterRequest("Test User", "test@example.com", "password123")
        authResponse = AuthResponse("fake-jwt-token", com.example.marketplace.dto.UserDto(1L, "Test User", "test@example.com", "USER"))
    }

    @Test
    fun `should login successfully`() {
        Mockito.`when`(authService.authenticate(authRequest)).thenReturn(authResponse)

        mockMvc.perform(post("/api/auth/login")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""{"email":"test@example.com","password":"password123"}"""))
            .andExpect(status().isOk)
    }

    @Test
    fun `should register successfully`() {
        Mockito.`when`(authService.register(registerRequest)).thenReturn(authResponse)

        mockMvc.perform(post("/api/auth/register")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""{"name":"Test User","email":"test@example.com","password":"password123"}"""))
            .andExpect(status().isOk)
    }
}