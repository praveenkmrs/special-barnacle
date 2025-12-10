package com.example.socialmedia.follow

import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/follows")
class FollowController(
    private val followService: FollowService
) {

    @PostMapping
    fun followUser(@RequestBody request: FollowRequest): ResponseEntity<FollowResponse> {
        val follow = followService.followUser(request)
        return ResponseEntity.ok(follow)
    }

    @DeleteMapping("/{followerId}/{followeeId}")
    fun unfollowUser(
        @PathVariable followerId: String,
        @PathVariable followeeId: String
    ): ResponseEntity<Unit> {
        followService.unfollowUser(followerId, followeeId)
        return ResponseEntity.noContent().build()
    }
}