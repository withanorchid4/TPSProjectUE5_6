# -*- encoding: utf-8 -*-
import ue

@ue.uclass()
class MyCharacter(ue.Character):
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        ue.LogWarning('%s ReceiveBeginPlay!' % self)
        controller = self.GetWorld().GetPlayerController()
        controller.UnPossess()
        controller.Possess(self)
        self.EnableInput(controller)

        self.InputComponent.BindAxis('MoveForward', self._move_forward)
        self.InputComponent.BindAxis('MoveRight', self._move_right)

    def _move_forward(self, value):
        if value != 0:
            self.AddMovementInput(self.GetActorForwardVector(), value)

    def _move_right(self, value):
        if value != 0:
            self.AddMovementInput(self.GetActorRightVector(), value)

